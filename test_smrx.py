#!/usr/bin/env python3
"""
Quick test of SMRX regex engine.
"""

import smrx
import os

print("=" * 60)
print("SMRX Regex Engine Test")
print("=" * 60)

# Test 1: Quick text search
print("\n[Test 1] Quick text search in string:")
text = """
def hello_world():
    print("Hello, World!")

def hello_universe():
    print("Hello, Universe!")
    
class HelloClass:
    pass
"""

results = smrx.quick_search(text, r'\bhello\w*', case_sensitive=False)
print(f"Pattern: r'\\bhello\\w*'")
print(f"Found {len(results)} matches:")
for r in results:
    print(f"  - '{r['match']}' at position {r['start']}")

# Test 2: Pattern validation
print("\n[Test 2] Pattern validation:")
valid_patterns = [
    r'def\s+\w+',
    r'\d{3}-\d{4}',
    r'[a-zA-Z]+@[a-zA-Z]+\.[a-zA-Z]+'
]
invalid_patterns = [
    r'[unclosed',
    r'(?P<incomplete',
    r'(?P<name>(?P<name>nested))'
]

for pattern in valid_patterns:
    is_valid, error = smrx.validate(pattern)
    status = "[OK] VALID" if is_valid else f"[ERR] INVALID: {error}"
    print(f"  {pattern:<40} {status}")

print("\nTesting invalid patterns:")
for pattern in invalid_patterns:
    is_valid, error = smrx.validate(pattern)
    status = "[OK] VALID" if is_valid else f"[ERR] INVALID"
    print(f"  {pattern:<40} {status}")

# Test 3: Extract groups
print("\n[Test 3] Extract groups from pattern:")
text = "John: 25, Jane: 30, Bob: 35"
pattern = r'(\w+):\s+(\d+)'
names = smrx.extract(text, pattern, group=1)
ages = smrx.extract(text, pattern, group=2)
print(f"Text: {text}")
print(f"Names (group 1): {names}")
print(f"Ages (group 2): {ages}")

# Test 4: Replace with pattern
print("\n[Test 4] Replace with pattern:")
text = "The year is 2024 and it's 2024!"
new_text, count = smrx.replace(text, r'\b2024\b', '2025')
print(f"Original: {text}")
print(f"Replaced: {new_text}")
print(f"Replacements made: {count}")

# Test 5: Directory search
print("\n[Test 5] Directory search (current directory):")
print(f"Searching in: {os.getcwd()}")
result = smrx.search(
    os.getcwd(),
    r'def\s+\w+\(',
    file_pattern="*.py",
    recursive=False,
    case_sensitive=True,
    max_results=20
)
print(f"Pattern: r'def\\s+\\w+\\('")
print(f"Files searched: {result.total_files_searched}")
print(f"Matches found: {result.matches_found}")
print(f"Execution time: {result.execution_time:.4f}s")
if result.matches:
    print(f"First 5 matches:")
    for match in result.matches[:5]:
        print(f"  {match.filepath}:{match.line_num}:{match.col_num} - {match.match_text}")

# Test 6: Cache stats
print("\n[Test 6] Cache statistics:")
cache_stats = smrx.get_cache_stats()  # Use get_cache_stats() instead of get_stats()
print(f"Pattern cache size: {cache_stats['pattern_cache']['size']}")
print(f"Pattern cache capacity: {cache_stats['pattern_cache']['capacity']}")
print(f"Match cache size: {cache_stats['match_cache']['size']}")
print(f"Match cache capacity: {cache_stats['match_cache']['capacity']}")
print(f"Search history size: {cache_stats['search_history_size']}")
print(f"Saved searches: {cache_stats['saved_searches']}")

print("\n" + "=" * 60)
print("SMRX Tests Complete!")
print("=" * 60)