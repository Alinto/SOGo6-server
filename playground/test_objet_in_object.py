class B:
    def __init__(self):
        self.b = 0

    def __repr__(self):
        return f"b= {self.b}"

class A:
    def __init__(self):
        self.b = B()


def changestep1(a:A):
    a.b.b = 5

a=A()
print(a.b)
changestep1(a)
print(a.b)
    