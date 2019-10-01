from abc import ABCMeta, abstractmethod


class AuthService:
    __metaclass__ = ABCMeta

    @abstractmethod
    def is_auth_request(self, source, msg):
        pass

    @abstractmethod
    def is_auth_confirmation(self, source, msg):
        pass


class Network:
    __metaclass__ = ABCMeta

    @abstractmethod
    def get_auth_service(self):
        pass


class Networks:
    @staticmethod
    def get_freenode():
        return Freenode()


class Freenode(Network):
    class _Nickserv(AuthService):

        def is_auth_request(self, source, msg):
            is_nickserv = self.__class__._is_nickserv(source)
            return is_nickserv and "identify via" in msg

        def is_auth_confirmation(self, source, msg):
            is_nickserv = self.__class__._is_nickserv(source)
            return is_nickserv and "now identified" in msg

        @staticmethod
        def _is_nickserv(source):
            return source == "NickServ!NickServ@services."

    def get_auth_service(self):
        return self._Nickserv()
