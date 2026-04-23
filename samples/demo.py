# demo.py

N = 5
MAG_LIMIT = 6.0

distances = [1.34, 2.64, 7.68, 11.3, 95.0]
magnitudes = [0.01, 1.46, 0.03, 1.14, 0.72]
sp_class = [3, 2, 3, 5, 2]


def abs_magnitude(app, dist):
    if dist <= 0.0:
        raise ValueError("Distance must be positive")
    if dist < 5.0:
        return app - 1.0
    if dist < 15.0:
        return app - 3.5
    return app - 8.0


def classify(cls):
    if cls == 2:
        print("     Type B  (blue-white)")
    elif cls == 3:
        print("     Type A  (white)")
    elif cls == 5:
        print("     Type G  (Sun-like)")
    return cls


def count_nearby(idx, limit):
    if idx >= N:
        return 0
    if distances[idx] < limit:
        return 1 + count_nearby(idx + 1, limit)
    return count_nearby(idx + 1, limit)


print("=== Stellar Survey ===\n")

passed = 0
failed = 0
i = 0

while i < N:
    mag = magnitudes[i]
    dist = distances[i]

    if mag > MAG_LIMIT:
        print(f"Star {i}: SKIPPED  mag = {mag}")
        failed += 1
        i += 1
        continue

    try:
        absmag = abs_magnitude(mag, dist)
        print(f"Star {i}:")
        print(f"     app mag  : {mag}")
        print(f"     distance : {dist} pc")
        print(f"     abs mag  : {absmag}")
        dummy = classify(sp_class[i])
        passed += 1
    except Exception as err:
        print(f"Star {i} ERROR: {err}")

    i += 1

print()
print(f"Passed: {passed}  Failed: {failed}")
print(f"Stars within 10 pc: {count_nearby(0, 10)}")
