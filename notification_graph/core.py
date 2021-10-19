from __future__ import annotations
from typing import List, Callable, Any


class NotificationType(object):
    def __init__(self, type_identifier, behavior: Callable[[Any, Any], None]):
        pass


class NotificationItem(object):

    def __init__(self, graph: NotificationGraph):
        self.__graph = graph
        self.__subscribe_list: List[NotificationItem] = []
        self.__observer_list: List[NotificationItem] = []

    @property
    def graph(self):
        return self.__graph

    def subscribe(self, item: NotificationItem):
        """Subscribe another notification item, typically when the subscribed item does some change,
        self will receive a signore.

        :param item: another notification item in same graph
        :return: False if already subscribed
        """
        assert self.__graph is item.__graph, 'can\'t subscribe item from different graph'
        if item not in self.__subscribe_list:
            self.__subscribe_list.append(item)
            item.__observer_list.append(self)
            return True
        return False

    def unsubscribe(self, item: NotificationItem):
        """
        :param item: another notification item in same graph
        :return: False if not subscribed yet
        """
        assert self.__graph is item.__graph, 'can\'t unsubscribe item from different graph'
        try:
            self.__subscribe_list.remove(item)
            item.__observer_list.remove(self)
        except ValueError:
            return False


class NotificationGraph(object):

    def __init__(self):
        pass
