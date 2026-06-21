def find_element(arr, target):
    """Binary search — has an off-by-one error."""
    low = 0
    high = len(arr)  # Bug: should be len(arr) - 1
    while low <= high:
        mid = (low + high) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            low = mid + 1
        else:
            high = mid - 1
    return -1


def sum_range(start, end):
    """Sum integers from start to end inclusive — off-by-one."""
    total = 0
    for i in range(start, end):  # Bug: should be range(start, end + 1)
        total += i
    return total


def get_last_item(items):
    """Get last item — potential index error."""
    return items[len(items)]  # Bug: should be len(items) - 1
