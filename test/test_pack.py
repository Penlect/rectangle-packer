
import rpack as hw

print(hw.helloworld())
print()

for a in dir(hw):
    if a.startswith('buildvalue_'):
        print('{:20}{!r:<20}{}'.format(a, getattr(hw, a)(), getattr(hw, a).__doc__))

print(hw.pack([(1,3)]))
test1 = [
    (12,32),
    (43,145),
    (123,56),
    (34,244),
    (54,234),
    (2,4)
]
test1 = list(sorted(test1, key=lambda x: -x[-1]))
print(test1)
print(hw.pack(test1))