def find_duplicates(items):
    """Find all duplicate items — O(n²) when O(n) is possible."""
    duplicates = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            if items[i] == items[j] and items[i] not in duplicates:
                duplicates.append(items[i])
    return duplicates


def search_all(data, queries):
    """Search for multiple queries — nested loop, no indexing."""
    results = []
    for query in queries:
        for item in data:
            if query.lower() in item.lower():
                results.append((query, item))
    return results


def read_and_process(filenames):
    """Reads files one by one, reopening each time."""
    all_lines = []
    for name in filenames:
        with open(name) as f:
            for line in f:
                all_lines.append(line.strip())
    # Then iterate again to count
    word_counts = {}
    for line in all_lines:
        for word in line.split():
            if word not in word_counts:
                word_counts[word] = 0
            word_counts[word] += 1
    return word_counts
