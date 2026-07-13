from abc import ABCMeta, abstractmethod
from typing import override

class A(metaclass=ABCMeta):
    """
    Abstract class for user source.
    All user source clients (ldap, sql, ...) should inherit from this class and implement its methods.
    """
    def __init__(self) -> None:
        """
        Just set a param to tell if the client needs to authenticate or not
        """
        self.foo = 1
        print("Init A")

    @abstractmethod
    def connect(self, banane:str) -> None:
        """
        _summary_

        :param banane: _description_
        :type banane: _type_
        """
        print("connect A" + banane)
    
    # @abstractmethod
    # def make_A(self) -> None:
    #     print("make A")

class B(metaclass=ABCMeta):
    """
    Abstract class for user source.
    All user source clients (ldap, sql, ...) should inherit from this class and implement its methods.
    """
    def __init__(self) -> None:
        """
        Just set a param to tell if the client needs to authenticate or not
        """
        self.foo = 999999
        print("Init B")

    @abstractmethod
    def connect(self, car:str) -> None:
        """
        _summary_

        :param car: _description_
        :type car: _type_
        """
        print("connect B" + car)
    
    # @abstractmethod
    # def make_B(self) -> None:
    #     print("make B")

class C(A, B):
    """
    _summary_

    :param A: _description_
    :type A: _type_
    :param B: _description_
    :type B: _type_
    """
    
    def __init__(self) -> None:
        """
        _summary_
        """
        A.__init__(self)
        B.__init__(self)
        print("init C")

    @override
    def connect(self, banane:str) -> None:
        """
        _summary_
        """
        print(self.foo)
    
    # def make_A(self):
    #     print("make A.C")
    
    # def make_B(self) -> None:
    #     print("make B.C")

    # def make_C(self):
    #     print("make C")

c = C()
# print(C.__mro__)
c.connect("test")
# c.make_A()
# c.make_B()
# c.make_C()