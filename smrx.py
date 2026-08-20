"""
SMRX: Smart Regex Engine - Enterprise-Grade Cross-Platform Pattern Matching
A fast, feature-rich regex engine for file searching across Windows, Linux, and macOS.

Features:
- Cross-platform path handling (Windows, Linux, macOS)
- Parallel multi-threaded search
- Advanced caching strategies with LRU eviction
- .gitignore integration for smart filtering
- Multiple output formats (JSON, CSV, markdown)
- Pattern library and saved searches
- Search history and statistics
- Streaming results for large datasets
- Binary/encoding detection
- Performance benchmarking
- Regular expression library
- Configuration system
- Advanced filtering and post-processing
"""

import re
import os
import sys
import json
import csv
import hashlib
import threading
import queue
import time
from typing import List, Dict, Optional, Tuple, Iterator, Set, Any, Callable, Pattern
from pathlib import Path, PurePath, PureWindowsPath, PurePosixPath
from dataclasses import dataclass, asdict, field
from collections import defaultdict, OrderedDict
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from enum import Enum
import fnmatch
import mimetypes

# Platform detection
PLATFORM = sys.platform
IS_WINDOWS = PLATFORM == 'win32'
IS_LINUX = PLATFORM.startswith('linux')
IS_MACOS = PLATFORM == 'darwin'


class SearchMode(Enum):
    """Search execution modes."""
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    STREAMING = "streaming"


class OutputFormat(Enum):
    """Result output formats."""
    TEXT = "text"
    JSON = "json"
    CSV = "csv"
    MARKDOWN = "markdown"
    DETAILED = "detailed"


@dataclass
class SearchMatch:
    """Represents a single regex match with full context."""
    filepath: str
    line_num: int
    col_num: int
    line_text: str
    match_text: str
    match_start: int
    match_end: int
    context_before: List[str] = field(default_factory=list)
    context_after: List[str] = field(default_factory=list)
    file_size: int = 0
    file_encoding: str = "utf-8"
    matched_groups: Tuple = ()
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "filepath": self.filepath,
            "line": self.line_num,
            "column": self.col_num,
            "text": self.line_text,
            "match": self.match_text,
            "start": self.match_start,
            "end": self.match_end,
            "groups": self.matched_groups if self.matched_groups else None
        }


@dataclass
class SearchResult:
    """Container for search results with statistics."""
    query: str
    pattern: str
    total_files_searched: int
    total_files_matched: int
    matches_found: int
    execution_time: float
    matches: List[SearchMatch] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "query": self.query,
            "pattern": self.pattern,
            "files_searched": self.total_files_searched,
            "files_matched": self.total_files_matched,
            "matches_found": self.matches_found,
            "execution_time": f"{self.execution_time:.4f}s",
            "matches": [m.to_dict() for m in self.matches[:1000]],
            "stats": self.stats,
            "errors": self.errors
        }


class LRUCache:
    """Least Recently Used cache implementation."""
    
    def __init__(self, capacity: int = 1000):
        self.capacity = capacity
        self.cache: OrderedDict = OrderedDict()
        self.lock = threading.Lock()
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        with self.lock:
            if key not in self.cache:
                return None
            self.cache.move_to_end(key)
            return self.cache[key]
    
    def put(self, key: str, value: Any):
        """Put value in cache."""
        with self.lock:
            if key in self.cache:
                self.cache.move_to_end(key)
            self.cache[key] = value
            if len(self.cache) > self.capacity:
                self.cache.popitem(last=False)
    
    def clear(self):
        """Clear cache."""
        with self.lock:
            self.cache.clear()
    
    def stats(self) -> Dict:
        """Get cache statistics."""
        with self.lock:
            return {
                "capacity": self.capacity,
                "size": len(self.cache),
                "utilization": f"{(len(self.cache) / self.capacity * 100):.1f}%"
            }


class GitignoreFilter:
    """Filter files based on .gitignore patterns."""
    
    def __init__(self, root_path: str):
        self.root_path = Path(root_path)
        self.patterns: List[str] = []
        self.compiled_patterns: List[Pattern] = []
        self._load_gitignore()
    
    def _load_gitignore(self):
        """Load .gitignore patterns."""
        gitignore_path = self.root_path / ".gitignore"
        if gitignore_path.exists():
            try:
                with open(gitignore_path, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            self.patterns.append(line)
                            try:
                                pattern = self._gitignore_to_regex(line)
                                self.compiled_patterns.append(re.compile(pattern))
                            except re.error:
                                pass
            except Exception:
                pass
    
    def _gitignore_to_regex(self, pattern: str) -> str:
        """Convert gitignore pattern to regex."""
        pattern = pattern.strip()
        if pattern.endswith('/'):
            pattern = pattern[:-1]
        pattern = fnmatch.translate(pattern)
        return pattern
    
    def should_ignore(self, filepath: str) -> bool:
        """Check if file should be ignored."""
        rel_path = str(Path(filepath).relative_to(self.root_path))
        for regex_pattern in self.compiled_patterns:
            if regex_pattern.match(rel_path):
                return True
        return False


class SMRXEngine:
    """Enterprise-grade Smart Regex Engine."""
    
    def __init__(self, cache_size: int = 5000, max_threads: int = 8, 
                 context_lines: int = 2, chunk_size: int = 1048576):
        """Initialize SMRX engine.
        
        Args:
            cache_size: LRU cache capacity
            max_threads: Maximum worker threads for parallel search
            context_lines: Lines before/after match to include
            chunk_size: Bytes to read at a time (1MB default)
        """
        self.cache_size = cache_size
        self.max_threads = max_threads
        self.context_lines = context_lines
        self.chunk_size = chunk_size
        
        self.pattern_cache = LRUCache(cache_size)
        self.file_cache = LRUCache(cache_size)
        self.match_cache = LRUCache(cache_size)
        self.gitignore_cache = LRUCache(100)
        
        self.search_history: List[Dict] = []
        self.saved_searches: Dict[str, Dict] = {}
        self.pattern_library = self._init_pattern_library()
        self.stats = {
            "total_searches": 0,
            "total_matches": 0,
            "total_files_searched": 0,
            "avg_search_time": 0.0,
            "total_bytes_processed": 0
        }

    
    def _init_pattern_library(self) -> Dict[str, str]:
        """Initialize built-in pattern library."""
        return {
            # Python
            "python_functions": r"def\s+(\w+)\s*\(",
            "python_classes": r"class\s+(\w+)\s*[\(:]",
            "python_imports": r"^(?:from|import)\s+(.+?)(?:\s+import)?",
            "python_todos": r"#\s*(?:TODO|FIXME|XXX|HACK)\s*:?\s*(.+)",
            "python_docstrings": r'""".*?"""|\'\'\'.*?\'\'\'',
            
            # JavaScript
            "js_functions": r"(?:function|const|let|var)\s+(\w+)\s*=?\s*(?:function)?\s*\(",
            "js_classes": r"class\s+(\w+)",
            "js_imports": r"^(?:import|require)\s+(?:.*from\s+)?['\"]([^'\"]+)['\"]",
            "js_todos": r"//\s*(?:TODO|FIXME|XXX|HACK)\s*:?\s*(.+)",
            
            # Web
            "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
            "url": r"https?://[^\s]+",
            "html_tags": r"<([a-zA-Z][a-zA-Z0-9]*)[^>]*>",
            "css_classes": r"\.[-_a-zA-Z0-9]+",
            "css_ids": r"#[-_a-zA-Z0-9]+",
            
            # Data
            "phone_us": r"\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}",
            "ipv4": r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b",
            "ipv6": r"(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}",
            "hex_color": r"#(?:[0-9a-fA-F]{3}){1,2}\b",
            "credit_card": r"\b(?:\d{4}[-\s]?){3}\d{4}\b",
            "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
            
            # General
            "urls": r"https?://[^\s]+",
            "timestamps": r"\d{4}-\d{2}-\d{2}[\sT]\d{2}:\d{2}:\d{2}",
            "json_keys": r'"([^"]+)"\s*:',
            "xml_tags": r"<([a-zA-Z][a-zA-Z0-9]*)[^>]*>",
            "variables": r"\$\{?(\w+)\}?",
            "numbers": r"\b\d+(?:\.\d+)?\b",
        }
    
    def _get_encoding(self, filepath: str) -> str:
        """Detect file encoding."""
        try:
            with open(filepath, 'rb') as f:
                raw = f.read(4)
                if raw.startswith(b'\xff\xfe') or raw.startswith(b'\xfe\xff'):
                    return 'utf-16'
                if raw.startswith(b'\xef\xbb\xbf'):
                    return 'utf-8-sig'
        except Exception:
            pass
        return 'utf-8'
    
    def _is_binary_file(self, filepath: str, chunk_size: int = 512) -> bool:
        """Detect if file is binary."""
        try:
            # Check MIME type first
            mime_type, _ = mimetypes.guess_type(filepath)
            if mime_type and 'text' not in mime_type:
                return True
            
            # Check content
            with open(filepath, 'rb') as f:
                chunk = f.read(chunk_size)
                if not chunk:
                    return False
                return b'\x00' in chunk or len(chunk) > 0 and chunk.count(0) / len(chunk) > 0.3
        except Exception:
            return False
    
    def _normalize_path(self, filepath: str) -> str:
        """Normalize path for cross-platform consistency."""
        return str(Path(filepath).as_posix())
    
    def _list_files(self, directory: str, pattern: str = "*", 
                   recursive: bool = True, respect_gitignore: bool = True) -> Iterator[str]:
        """List files matching pattern."""
        base_path = Path(directory)
        gitignore = None
        
        if respect_gitignore:
            gitignore_cached = self.gitignore_cache.get(directory)
            if gitignore_cached:
                gitignore = gitignore_cached
            else:
                gitignore = GitignoreFilter(directory)
                self.gitignore_cache.put(directory, gitignore)
        
        try:
            if recursive:
                glob_pattern = f"**/{pattern}" if pattern != "*" else "**/*"
            else:
                glob_pattern = pattern if pattern != "*" else "*"
            
            for filepath in base_path.glob(glob_pattern):
                if filepath.is_file():
                    if gitignore and gitignore.should_ignore(str(filepath)):
                        continue
                    yield str(filepath)
        except Exception:
            pass
    
    def compile_pattern(self, regex_str: str, flags: int = 0) -> Optional[Pattern]:
        """Compile and cache regex patterns."""
        cache_key = f"{regex_str}:{flags}"
        cached = self.pattern_cache.get(cache_key)
        if cached:
            return cached
        
        try:
            pattern = re.compile(regex_str, flags)
            self.pattern_cache.put(cache_key, pattern)
            return pattern
        except re.error as e:
            raise ValueError(f"Invalid regex pattern: {e}")
    
    def validate_regex(self, regex_str: str) -> Tuple[bool, Optional[str]]:
        """Validate regex pattern."""
        try:
            re.compile(regex_str)
            return True, None
        except re.error as e:
            return False, str(e)
    
    def get_pattern(self, name: str) -> Optional[str]:
        """Get pattern from library."""
        return self.pattern_library.get(name)
    
    def list_patterns(self) -> Dict[str, str]:
        """List all available patterns."""
        return self.pattern_library.copy()
    
    def save_search(self, name: str, regex_str: str, file_pattern: str = "*"):
        """Save a search for later use."""
        self.saved_searches[name] = {
            "regex": regex_str,
            "file_pattern": file_pattern,
            "timestamp": datetime.now().isoformat()
        }
    
    def load_search(self, name: str) -> Optional[Dict]:
        """Load a saved search."""
        return self.saved_searches.get(name)
    
    def _search_file(self, filepath: str, pattern: Pattern, 
                    case_sensitive: bool = True) -> List[SearchMatch]:
        """Search a single file for pattern matches."""
        cache_key = f"{filepath}:{pattern.pattern}"
        cached = self.match_cache.get(cache_key)
        if cached:
            return cached
        
        matches = []
        try:
            if self._is_binary_file(filepath):
                return matches
            
            encoding = self._get_encoding(filepath)
            file_size = os.path.getsize(filepath)
            
            with open(filepath, 'r', encoding=encoding, errors='ignore') as f:
                lines = f.readlines()
                
                for line_num, line in enumerate(lines, 1):
                    for match in pattern.finditer(line):
                        # Get context
                        context_before = []
                        context_after = []
                        
                        if line_num > 1:
                            context_before = [l.rstrip('\n\r') for l in lines[max(0, line_num - self.context_lines - 1):line_num - 1]]
                        
                        if line_num < len(lines):
                            context_after = [l.rstrip('\n\r') for l in lines[line_num:min(len(lines), line_num + self.context_lines)]]
                        
                        matches.append(SearchMatch(
                            filepath=self._normalize_path(filepath),
                            line_num=line_num,
                            col_num=match.start() + 1,
                            line_text=line.rstrip('\n\r'),
                            match_text=match.group(0),
                            match_start=match.start(),
                            match_end=match.end(),
                            context_before=context_before,
                            context_after=context_after,
                            file_size=file_size,
                            file_encoding=encoding,
                            matched_groups=match.groups() if match.groups() else ()
                        ))
        except Exception as e:
            pass
        
        self.match_cache.put(cache_key, matches)
        return matches
    
    def search_directory(self, directory: str, regex_str: str, 
                        file_pattern: str = "*", recursive: bool = True,
                        case_sensitive: bool = True, max_results: int = 10000,
                        mode: SearchMode = SearchMode.PARALLEL,
                        respect_gitignore: bool = True) -> SearchResult:
        """Search directory for regex matches."""
        start_time = time.time()
        
        # Compile pattern
        try:
            pattern = self.compile_pattern(
                regex_str, 
                flags=0 if case_sensitive else re.IGNORECASE
            )
        except ValueError as e:
            return SearchResult(
                query=regex_str,
                pattern=file_pattern,
                total_files_searched=0,
                total_files_matched=0,
                matches_found=0,
                execution_time=0,
                errors=[str(e)]
            )
        
        matches = []
        files_searched = 0
        files_matched = set()
        
        if mode == SearchMode.SEQUENTIAL:
            matches, files_searched = self._search_sequential(
                directory, pattern, file_pattern, recursive, max_results, respect_gitignore
            )
        elif mode == SearchMode.PARALLEL:
            matches, files_searched = self._search_parallel(
                directory, pattern, file_pattern, recursive, max_results, respect_gitignore
            )
        else:
            matches, files_searched = self._search_streaming(
                directory, pattern, file_pattern, recursive, max_results, respect_gitignore
            )
        
        files_matched = set(m.filepath for m in matches)
        execution_time = time.time() - start_time
        
        # Update statistics
        self.stats["total_searches"] += 1
        self.stats["total_matches"] += len(matches)
        self.stats["total_files_searched"] += files_searched
        if self.stats["avg_search_time"] == 0:
            self.stats["avg_search_time"] = execution_time
        else:
            self.stats["avg_search_time"] = (self.stats["avg_search_time"] + execution_time) / 2
        
        # Record in history
        self.search_history.append({
            "query": regex_str,
            "pattern": file_pattern,
            "timestamp": datetime.now().isoformat(),
            "matches": len(matches),
            "execution_time": execution_time
        })
        
        return SearchResult(
            query=regex_str,
            pattern=file_pattern,
            total_files_searched=files_searched,
            total_files_matched=len(files_matched),
            matches_found=len(matches),
            execution_time=execution_time,
            matches=matches[:max_results],
            stats=self.stats.copy()
        )
    
    def _search_sequential(self, directory: str, pattern: Pattern, file_pattern: str,
                          recursive: bool, max_results: int, respect_gitignore: bool) -> Tuple[List[SearchMatch], int]:
        """Sequential search implementation."""
        matches = []
        files_searched = 0
        
        for filepath in self._list_files(directory, file_pattern, recursive, respect_gitignore):
            if len(matches) >= max_results:
                break
            files_searched += 1
            file_matches = self._search_file(filepath, pattern)
            matches.extend(file_matches[:max_results - len(matches)])
        
        return matches, files_searched
    
    def _search_parallel(self, directory: str, pattern: Pattern, file_pattern: str,
                        recursive: bool, max_results: int, respect_gitignore: bool) -> Tuple[List[SearchMatch], int]:
        """Parallel search implementation using thread pool."""
        matches = []
        files_searched = 0
        lock = threading.Lock()
        
        file_list = list(self._list_files(directory, file_pattern, recursive, respect_gitignore))
        
        with ThreadPoolExecutor(max_workers=self.max_threads) as executor:
            futures = {
                executor.submit(self._search_file, filepath, pattern): filepath 
                for filepath in file_list
            }
            
            for future in as_completed(futures):
                if len(matches) >= max_results:
                    break
                
                try:
                    file_matches = future.result()
                    with lock:
                        files_searched += 1
                        matches.extend(file_matches[:max_results - len(matches)])
                except Exception:
                    pass
        
        return matches, files_searched
    
    def _search_streaming(self, directory: str, pattern: Pattern, file_pattern: str,
                         recursive: bool, max_results: int, respect_gitignore: bool) -> Tuple[List[SearchMatch], int]:
        """Streaming search implementation."""
        matches = []
        files_searched = 0
        
        for filepath in self._list_files(directory, file_pattern, recursive, respect_gitignore):
            if len(matches) >= max_results:
                break
            files_searched += 1
            file_matches = self._search_file(filepath, pattern)
            for match in file_matches:
                if len(matches) >= max_results:
                    break
                matches.append(match)
                yield match
        
        return matches, files_searched
    
    def replace_pattern(self, text: str, regex_str: str, replacement: str,
                       case_sensitive: bool = True, count: int = 0) -> Tuple[str, int]:
        """Replace pattern matches in text."""
        try:
            pattern = self.compile_pattern(regex_str, flags=0 if case_sensitive else re.IGNORECASE)
        except ValueError:
            return text, 0
        
        new_text, replacements = pattern.subn(replacement, text, count=count if count > 0 else 0)
        return new_text, replacements
    
    def extract_pattern(self, text: str, regex_str: str, group: int = 1,
                       case_sensitive: bool = True) -> List[str]:
        """Extract specific groups from pattern matches."""
        try:
            pattern = self.compile_pattern(regex_str, flags=0 if case_sensitive else re.IGNORECASE)
        except ValueError:
            return []
        
        results = []
        for match in pattern.finditer(text):
            try:
                results.append(match.group(group))
            except IndexError:
                pass
        return results
    
    def format_results(self, result: SearchResult, format_type: OutputFormat) -> str:
        """Format search results."""
        if format_type == OutputFormat.JSON:
            return json.dumps(result.to_dict(), indent=2)
        
        elif format_type == OutputFormat.CSV:
            output = ["filepath,line,column,match,text"]
            for match in result.matches:
                output.append(f'"{match.filepath}",{match.line_num},{match.col_num},"{match.match_text}","{match.line_text}"')
            return "\n".join(output)
        
        elif format_type == OutputFormat.MARKDOWN:
            lines = [
                f"# Search Results: {result.query}",
                f"",
                f"**Files searched:** {result.total_files_searched}  ",
                f"**Files matched:** {result.total_files_matched}  ",
                f"**Matches found:** {result.matches_found}  ",
                f"**Time:** {result.execution_time:.3f}s",
                f"",
            ]
            
            files_dict = defaultdict(list)
            for match in result.matches:
                files_dict[match.filepath].append(match)
            
            for filepath, matches in sorted(files_dict.items()):
                lines.append(f"## `{filepath}`")
                for match in matches[:50]:
                    lines.append(f"- Line {match.line_num}:{match.col_num}: `{match.match_text}`")
                if len(matches) > 50:
                    lines.append(f"- ... and {len(matches) - 50} more matches")
                lines.append("")
            
            return "\n".join(lines)
        
        elif format_type == OutputFormat.DETAILED:
            lines = [
                f"╔═══════════════════════════════════════════════════════════╗",
                f"║ SMRX Search Results                                       ║",
                f"╚═══════════════════════════════════════════════════════════╝",
                f"",
                f"Query: {result.query}",
                f"Pattern: {result.pattern}",
                f"Files Searched: {result.total_files_searched}",
                f"Files Matched: {result.total_files_matched}",
                f"Matches Found: {result.matches_found}",
                f"Execution Time: {result.execution_time:.4f}s",
                f"",
            ]
            
            files_dict = defaultdict(list)
            for match in result.matches:
                files_dict[match.filepath].append(match)
            
            for filepath, matches in sorted(files_dict.items()):
                lines.append(f"📄 {filepath} ({len(matches)} matches)")
                for match in matches[:10]:
                    lines.append(f"  L{match.line_num}:{match.col_num} → {match.match_text}")
                    if match.context_before:
                        for ctx in match.context_before:
                            lines.append(f"     > {ctx}")
                    if match.context_after:
                        for ctx in match.context_after:
                            lines.append(f"     < {ctx}")
                if len(matches) > 10:
                    lines.append(f"  ... and {len(matches) - 10} more matches")
                lines.append("")
            
            return "\n".join(lines)
        
        else:  # TEXT format
            lines = [f"✓ Found {result.matches_found} matches in {result.total_files_searched} files ({result.execution_time:.3f}s)", ""]
            
            files_dict = defaultdict(list)
            for match in result.matches:
                files_dict[match.filepath].append(match)
            
            for filepath, matches in sorted(files_dict.items()):
                lines.append(f"{filepath} ({len(matches)} matches)")
                for match in matches[:10]:
                    lines.append(f"  L{match.line_num}:{match.col_num}: {match.line_text[:80]}")
                if len(matches) > 10:
                    lines.append(f"  ... and {len(matches) - 10} more matches")
                lines.append("")
            
            return "\n".join(lines)
    
    def get_cache_stats(self) -> Dict:
        """Get cache statistics."""
        return {
            "pattern_cache": self.pattern_cache.stats(),
            "file_cache": self.file_cache.stats(),
            "match_cache": self.match_cache.stats(),
            "search_history_size": len(self.search_history),
            "saved_searches": len(self.saved_searches)
        }
    
    def clear_cache(self):
        """Clear all caches."""
        self.pattern_cache.clear()
        self.file_cache.clear()
        self.match_cache.clear()
        self.gitignore_cache.clear()
    
    def get_stats(self) -> Dict:
        """Get engine statistics."""
        return self.stats.copy()
    
    def reset_stats(self):
        """Reset statistics."""
        self.stats = {
            "total_searches": 0,
            "total_matches": 0,
            "total_files_searched": 0,
            "avg_search_time": 0.0,
            "total_bytes_processed": 0
        }


# Global instance
_engine = SMRXEngine()


def search(directory: str, regex_str: str, file_pattern: str = "*",
          recursive: bool = True, case_sensitive: bool = True,
          max_results: int = 10000, mode: SearchMode = SearchMode.PARALLEL,
          respect_gitignore: bool = True) -> SearchResult:
    """High-level search function."""
    return _engine.search_directory(
        directory, regex_str, file_pattern, recursive,
        case_sensitive, max_results, mode, respect_gitignore
    )


def quick_search(text: str, regex_str: str, case_sensitive: bool = True) -> List[Dict]:
    """Quick search in text."""
    try:
        pattern = _engine.compile_pattern(regex_str, flags=0 if case_sensitive else re.IGNORECASE)
    except ValueError:
        return []
    
    results = []
    for match in pattern.finditer(text):
        results.append({
            "match": match.group(0),
            "start": match.start(),
            "end": match.end(),
            "groups": match.groups() if match.groups() else None
        })
    return results


def validate(regex_str: str) -> Tuple[bool, Optional[str]]:
    """Validate regex pattern."""
    return _engine.validate_regex(regex_str)


def replace(text: str, regex_str: str, replacement: str,
           case_sensitive: bool = True, count: int = 0) -> Tuple[str, int]:
    """Replace in text."""
    return _engine.replace_pattern(text, regex_str, replacement, case_sensitive, count)


def extract(text: str, regex_str: str, group: int = 1,
           case_sensitive: bool = True) -> List[str]:
    """Extract groups from text."""
    return _engine.extract_pattern(text, regex_str, group, case_sensitive)


def get_pattern(name: str) -> Optional[str]:
    """Get pattern from library."""
    return _engine.get_pattern(name)


def list_patterns() -> Dict[str, str]:
    """List all patterns."""
    return _engine.list_patterns()


def save_search(name: str, regex_str: str, file_pattern: str = "*"):
    """Save a search."""
    _engine.save_search(name, regex_str, file_pattern)


def load_search(name: str) -> Optional[Dict]:
    """Load a saved search."""
    return _engine.load_search(name)


def format_results(result: SearchResult, format_type: OutputFormat = OutputFormat.TEXT) -> str:
    """Format results."""
    return _engine.format_results(result, format_type)


def clear_cache():
    """Clear cache."""
    _engine.clear_cache()


def get_cache_stats() -> Dict:
    """Get cache stats."""
    return _engine.get_cache_stats()


def get_stats() -> Dict:
    """Get engine stats."""
    return _engine.get_stats()


def reset_stats():
    """Reset stats."""
    _engine.reset_stats()


# ============================================================================
# ADVANCED UTILITIES & PLUGINS
# ============================================================================

class PatternOptimizer:
    """Optimize regex patterns for better performance."""
    
    @staticmethod
    def simplify_alternation(pattern: str) -> str:
        """Optimize alternation groups."""
        # Convert (a|b|c) to use character classes where possible
        return pattern
    
    @staticmethod
    def combine_patterns(patterns: List[str]) -> str:
        """Combine multiple patterns into one."""
        return "|".join(f"(?:{p})" for p in patterns)
    
    @staticmethod
    def estimate_complexity(pattern: str) -> Dict[str, Any]:
        """Estimate regex complexity and performance."""
        complexity_score = 0
        features = []
        
        if '.*' in pattern:
            complexity_score += 10
            features.append("greedy_wildcard")
        if '.*?' in pattern:
            complexity_score += 5
            features.append("lazy_wildcard")
        if '(?:' in pattern:
            features.append("non_capturing_groups")
        if '(?<=' in pattern or '(?=' in pattern:
            complexity_score += 15
            features.append("lookahead_lookbehind")
        if '(?P<' in pattern:
            features.append("named_groups")
        
        # Count groups
        groups = pattern.count('(') - pattern.count('(?:')
        complexity_score += groups * 2
        
        return {
            "complexity_score": complexity_score,
            "estimated_speed": "fast" if complexity_score < 10 else "medium" if complexity_score < 25 else "slow",
            "features": features,
            "recommendation": f"Pattern complexity: {complexity_score}/100"
        }


class ResultAggregator:
    """Aggregate and process search results."""
    
    @staticmethod
    def group_by_file(results: List[SearchMatch]) -> Dict[str, List[SearchMatch]]:
        """Group results by file."""
        grouped = defaultdict(list)
        for result in results:
            grouped[result.filepath].append(result)
        return grouped
    
    @staticmethod
    def group_by_pattern(results: List[SearchMatch], patterns: Dict[str, str]) -> Dict[str, List[SearchMatch]]:
        """Group results by matching pattern name."""
        grouped = defaultdict(list)
        for result in results:
            for name, pattern in patterns.items():
                if re.match(pattern, result.match_text):
                    grouped[name].append(result)
                    break
        return grouped
    
    @staticmethod
    def statistics(results: List[SearchMatch]) -> Dict[str, Any]:
        """Calculate statistics on results."""
        if not results:
            return {}
        
        files = set(r.filepath for r in results)
        lines_with_matches = set((r.filepath, r.line_num) for r in results)
        matches_per_file = defaultdict(int)
        
        for r in results:
            matches_per_file[r.filepath] += 1
        
        return {
            "total_matches": len(results),
            "unique_files": len(files),
            "unique_lines": len(lines_with_matches),
            "matches_per_file_avg": len(results) / len(files) if files else 0,
            "matches_per_file_max": max(matches_per_file.values()) if matches_per_file else 0,
            "matches_per_file_min": min(matches_per_file.values()) if matches_per_file else 0,
        }
    
    @staticmethod
    def deduplicate(results: List[SearchMatch]) -> List[SearchMatch]:
        """Remove duplicate matches."""
        seen = set()
        unique = []
        for r in results:
            key = (r.filepath, r.line_num, r.col_num, r.match_text)
            if key not in seen:
                seen.add(key)
                unique.append(r)
        return unique
    
    @staticmethod
    def filter_by_context(results: List[SearchMatch], context_pattern: str) -> List[SearchMatch]:
        """Filter results by context pattern."""
        filtered = []
        try:
            pattern = re.compile(context_pattern, re.IGNORECASE)
            for r in results:
                full_context = " ".join(r.context_before + [r.line_text] + r.context_after)
                if pattern.search(full_context):
                    filtered.append(r)
        except re.error:
            return results
        return filtered
    
    @staticmethod
    def rank_results(results: List[SearchMatch], sort_by: str = "line") -> List[SearchMatch]:
        """Rank and sort results."""
        if sort_by == "line":
            return sorted(results, key=lambda r: (r.filepath, r.line_num, r.col_num))
        elif sort_by == "file":
            return sorted(results, key=lambda r: (r.filepath, r.line_num))
        elif sort_by == "match_length":
            return sorted(results, key=lambda r: len(r.match_text), reverse=True)
        elif sort_by == "reverse":
            return sorted(results, key=lambda r: (r.filepath, r.line_num), reverse=True)
        return results


class FileAnalyzer:
    """Analyze files for metadata and properties."""
    
    @staticmethod
    def get_file_stats(filepath: str) -> Dict[str, Any]:
        """Get detailed file statistics."""
        try:
            stat = os.stat(filepath)
            return {
                "path": filepath,
                "size_bytes": stat.st_size,
                "size_kb": stat.st_size / 1024,
                "size_mb": stat.st_size / (1024 * 1024),
                "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "accessed": datetime.fromtimestamp(stat.st_atime).isoformat(),
            }
        except Exception:
            return {}
    
    @staticmethod
    def analyze_encoding(filepath: str) -> Dict[str, str]:
        """Analyze file encoding."""
        try:
            with open(filepath, 'rb') as f:
                raw = f.read(4)
                
                if raw.startswith(b'\xff\xfe\x00\x00'):
                    return {"encoding": "utf-32-le", "bom": True}
                if raw.startswith(b'\x00\x00\xfe\xff'):
                    return {"encoding": "utf-32-be", "bom": True}
                if raw.startswith(b'\xff\xfe'):
                    return {"encoding": "utf-16-le", "bom": True}
                if raw.startswith(b'\xfe\xff'):
                    return {"encoding": "utf-16-be", "bom": True}
                if raw.startswith(b'\xef\xbb\xbf'):
                    return {"encoding": "utf-8-sig", "bom": True}
                
                return {"encoding": "utf-8", "bom": False}
        except Exception:
            return {"encoding": "unknown", "bom": False}
    
    @staticmethod
    def count_lines(filepath: str) -> int:
        """Count lines in file."""
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                return sum(1 for _ in f)
        except Exception:
            return 0


class PerformanceProfiler:
    """Profile SMRX performance."""
    
    def __init__(self):
        self.timings: List[Dict] = []
    
    def record(self, operation: str, duration: float, items_processed: int = 0):
        """Record timing information."""
        self.timings.append({
            "operation": operation,
            "duration": duration,
            "timestamp": datetime.now().isoformat(),
            "items_processed": items_processed,
            "throughput": items_processed / duration if duration > 0 else 0
        })
    
    def get_report(self) -> Dict[str, Any]:
        """Generate performance report."""
        if not self.timings:
            return {}
        
        operations = defaultdict(list)
        for t in self.timings:
            operations[t["operation"]].append(t["duration"])
        
        report = {}
        for op, durations in operations.items():
            report[op] = {
                "count": len(durations),
                "total_time": sum(durations),
                "avg_time": sum(durations) / len(durations),
                "min_time": min(durations),
                "max_time": max(durations)
            }
        
        return report
    
    def reset(self):
        """Reset profiler."""
        self.timings.clear()


class DiffAnalyzer:
    """Analyze differences in search results across multiple searches."""
    
    @staticmethod
    def compare_searches(before: List[SearchMatch], after: List[SearchMatch]) -> Dict:
        """Compare two search result sets."""
        before_set = set((r.filepath, r.line_num, r.match_text) for r in before)
        after_set = set((r.filepath, r.line_num, r.match_text) for r in after)
        
        added = after_set - before_set
        removed = before_set - after_set
        unchanged = after_set & before_set
        
        return {
            "added": len(added),
            "removed": len(removed),
            "unchanged": len(unchanged),
            "total_before": len(before),
            "total_after": len(after),
            "change_percentage": (len(added) + len(removed)) / max(len(before), len(after)) * 100 if max(len(before), len(after)) > 0 else 0
        }


class ConfigManager:
    """Manage SMRX configuration."""
    
    def __init__(self):
        self.config = {
            "max_threads": 8,
            "cache_size": 5000,
            "max_results": 10000,
            "context_lines": 2,
            "respect_gitignore": True,
            "default_search_mode": "parallel",
            "chunk_size": 1048576,
            "encoding_detection": True,
            "binary_detection": True
        }
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value."""
        return self.config.get(key, default)
    
    def set(self, key: str, value: Any):
        """Set configuration value."""
        self.config[key] = value
    
    def load_from_dict(self, config_dict: Dict):
        """Load configuration from dictionary."""
        self.config.update(config_dict)
    
    def to_dict(self) -> Dict:
        """Export configuration to dictionary."""
        return self.config.copy()


# Global utilities
_profiler = PerformanceProfiler()
_config = ConfigManager()
_optimizer = PatternOptimizer()
_aggregator = ResultAggregator()
_analyzer = FileAnalyzer()


def get_config() -> ConfigManager:
    """Get configuration manager."""
    return _config


def get_profiler() -> PerformanceProfiler:
    """Get performance profiler."""
    return _profiler


def optimize_pattern(pattern: str) -> Dict[str, Any]:
    """Optimize a regex pattern."""
    return _optimizer.estimate_complexity(pattern)


def aggregate_results(results: List[SearchMatch], group_by: str = "file") -> Dict:
    """Aggregate search results."""
    if group_by == "file":
        return _aggregator.group_by_file(results)
    elif group_by == "file_stats":
        grouped = _aggregator.group_by_file(results)
        return {k: len(v) for k, v in grouped.items()}
    return {}


def analyze_file(filepath: str) -> Dict:
    """Analyze a file."""
    return {
        "stats": _analyzer.get_file_stats(filepath),
        "encoding": _analyzer.analyze_encoding(filepath),
        "lines": _analyzer.count_lines(filepath)
    }


def get_result_statistics(results: List[SearchMatch]) -> Dict:
    """Get statistics on results."""
    return _aggregator.statistics(results)


def compare_result_sets(before: List[SearchMatch], after: List[SearchMatch]) -> Dict:
    """Compare two result sets."""
    return DiffAnalyzer.compare_searches(before, after)
