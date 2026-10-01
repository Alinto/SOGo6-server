class A:
    def __init__(self, a):
        self.a = a

a = A("hello")

def func(a):
    b = a
    b.a = "Banane"

print(a.a)
func(a)
print(a.a)