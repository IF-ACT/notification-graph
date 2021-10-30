from .util import check_type
from typing import Iterable, Callable, Any, Union, Tuple, Dict, Set

# only for typing hint
# noinspection PyUnreachableCode
if False:
    # noinspection PyUnresolvedReferences
    from .core import NotificationItem, NotificationType, NotificationGraph, \
        NotificationAttributeSetHandle, NotificationAttributeSet


class INotificationBehaviorInterface:
    """Interface of all notification behaviors."""

    def get_interested_attributes(self) -> Iterable[str]:
        """Once an attribute registered here,
        `set_attribute` will be invoked before set the attribute even if the item do not have this behavior.

        Notice this will be only get once when the behavior first appears in a graph, changing the return value
        makes no sense during runtime.
        """
        return []

    def get_attribute(self, handle, attribute_name: str):
        """Called when gathering an attribute by name on notification.

        :param handle:
        :type handle NotificationAttributeSetHandle
        :param attribute_name: name of attribute
        :return: value of the attribute
        :raise NameError: this behavior does not handle given attribute
        """

    def set_attribute(self, handle, attribute_name: str, attribute_value):
        """Called when an attribute is set on notification.

        :param handle:
        :type handle: NotificationAttributeSetHandle
        :param attribute_name: name of attribute
        :param attribute_value: new value of the attribute
        :raise NameError: this behavior does not handle given attribute
        """

    def pre_subscribe(self, subscriber_item, notifier_item, related_identifiers: set):
        """Called before a new subscription established.

        :param subscriber_item:
        :type subscriber_item: NotificationItem
        :param notifier_item:
        :type notifier_item: NotificationItem
        :param related_identifiers: if any notification type declared with an identifier and a behavior is in current
            graph, then we say the identifier is related to the behavior in this graph
        """

    def pre_unsubscribe(self, subscriber_item, notifier_item, related_identifiers: set):
        """Called before subscriber item unsubscribes an item.

        :param subscriber_item:
        :type subscriber_item: NotificationItem
        :param notifier_item:
        :type notifier_item: NotificationItem
        :param related_identifiers: if any notification type declared with an identifier and a behavior is in current
            graph, then we say the identifier is related to the behavior in this graph
        """

    def __repr__(self):
        return f'<notification behavior {self.__str__()}>'

    def __str__(self):
        return self.__class__.__name__


class NotifySubscribers(INotificationBehaviorInterface):
    """Notify subscriber items with a given attribute.

    When an item set the attribute to True, all item subscribing it will also set the attribute to true.
    """

    def __init__(self, attribute_name: str = 'activate'):
        """
        :param attribute_name: value type of this attribute should be bool
        """
        self.__attribute_name = attribute_name

    def get_attribute(self, handle, attribute_name: str):
        if attribute_name == self.__attribute_name:
            return self.__get_gathered_value(handle.attribute_set)
        else:
            raise NameError()

    def set_attribute(self, handle, attribute_name: str, attribute_value: bool):
        if attribute_name == self.__attribute_name:
            check_type(attribute_value, bool)
            old_gathered_value = self.__get_gathered_value(handle.attribute_set)
            handle.attribute_set.set_attribute(self.__attribute_name, attribute_value)
            if self.__get_gathered_value(handle.attribute_set) == old_gathered_value:
                return
            if attribute_value:
                for item in handle.item.subscriber_items:
                    self.__recursive_set_true(item, handle.identifier)
            else:
                for item in handle.item.subscriber_items:
                    self.__recursive_set_false(item, handle.identifier)
        else:
            raise NameError()

    def pre_subscribe(self, subscriber_item, notifier_item, related_identifiers: set):
        for identifier in related_identifiers:
            attribute_set = notifier_item.get_attribute_set(identifier)
            if attribute_set is None:
                continue
            if self.__get_gathered_value(attribute_set):
                self.__recursive_set_true(subscriber_item, identifier)

    def pre_unsubscribe(self, subscriber_item, notifier_item, related_identifiers: set):
        pass

    def __get_gathered_value(self, attribute_set):
        return attribute_set.get_attribute(self.__attribute_name, False) or \
               attribute_set.get_cache(self.__attribute_name, False)

    def __recursive_set_true(self, item, identifier):
        """:type item: NotificationItem"""
        attribute_set = item.get_attribute_set(identifier, True)
        if attribute_set.get_cache(self.__attribute_name, False):
            return
        attribute_set.set_cache(self.__attribute_name, True)
        for i in item.subscriber_items:
            self.__recursive_set_true(i, identifier)

    def __recursive_set_false(self, item, identifier):
        """:type item: NotificationItem"""
        attribute_set = item.get_attribute_set(identifier)
        if attribute_set is None or not attribute_set.get_cache(self.__attribute_name, False):
            return
        for notifier in item.notifier_items:
            notifier_attribute_set = notifier.get_attribute_set(identifier)
            if notifier_attribute_set is not None and self.__get_gathered_value(notifier_attribute_set):
                return
        attribute_set.set_cache(self.__attribute_name, False)
        for i in item.subscriber_items:
            self.__recursive_set_false(i, identifier)


class CountAttribute(INotificationBehaviorInterface):

    def __init__(self, **attributes: Union[str, Tuple[str, Callable[[Any], int]]]):
        """
        :param prefix: prefix used to get count. e.g. the count of attribute 'activate' will be saved in attribute
            'count_activate'
        :param attributes:
            - key: name of the attribute to count
            - value:
             str: name of an attribute to store the count (use default_count_function to count attribute)
             tuple: the first item same as str, the second item is how to count the attribute, key is attribute name,
                value should be a function that receives the value of attribute and returns an int as count.
        """
        self.__storages: Set[str] = set()

        hint = 'should be either str or tuple of str and callable'
        for attribute, value in attributes.items():
            if isinstance(value, str):
                attribute_name = value
                attributes[attribute] = (value, lambda v: self.default_count_function(v))
                # use lambda to allow set default function
            elif isinstance(value, tuple):
                assert len(value) == 2 and isinstance(value[0], str) and callable(value[1]), \
                    f'wrong format of parameter {repr(attribute)}: {repr(value)}, {hint}'
                attribute_name = value[0]
            else:
                raise TypeError(f'unknown parameter type: {repr(value)}, {hint}')

            assert attribute_name not in attributes, \
                f'count storage attribute name {repr(attribute_name)} conflicts with counted attribute'
            self.__storages.add(attribute_name)

        self.__attributes: Dict[str, Tuple[str, Callable[[Any], int]]] = attributes
        '''key: attribute name
        value: (count attribute name, count function)'''

    def get_interested_attributes(self) -> Iterable[str]:
        return self.__attributes.keys()

    def get_attribute(self, handle, attribute_name: str):
        if attribute_name not in self.__storages:
            raise NameError()
        return self.__calculate_total(handle.attribute_set, attribute_name)

    def set_attribute(self, handle, attribute_name: str, attribute_value):
        if attribute_name in self.__storages:   # directly set count
            check_type(attribute_value, int)
            attribute_set = handle.item.get_attribute_set(handle.identifier, True)
            old_value = attribute_set.get_attribute(attribute_name, 0)
            attribute_set.set_attribute(attribute_name, attribute_value)
            for subscriber in handle.item.subscriber_items:
                self.__recursive_modify_count(
                    subscriber, handle.identifier, attribute_name, attribute_value - old_value)

        elif count_info := self.__attributes.get(attribute_name, None):     # on interested attribute set
            count_name, count_function = count_info
            attribute_set = handle.item.get_attribute_set(handle.identifier)
            if attribute_set is None or not attribute_set.has_attribute(attribute_name):
                self.__recursive_modify_count(
                    handle.item, handle.identifier, count_name, count_function(attribute_value))
            else:
                old_value = attribute_set.get_attribute(attribute_name)
                self.__recursive_modify_count(
                    handle.item, handle.identifier, count_name,
                    count_function(attribute_value) - count_function(old_value)
                )

        else:
            raise NameError()

    @staticmethod
    def default_count_function(value):
        """If value is int, will be take as count, else will regard bool(value) true as 1, false as 0."""
        if isinstance(value, int):
            return value
        else:
            return 1 if value else 0

    @staticmethod
    def __calculate_total(attribute_set, attribute_name: str):
        return attribute_set.get_attribute(attribute_name, 0) + attribute_set.get_cache(attribute_name, 0)

    @staticmethod
    def __recursive_modify_count(item, identifier, count_name: str, delta: int, visited=None):
        """:type item: NotificationItem"""
        if visited is None:
            visited = set()
        if delta == 0 or item in visited:
            return
        visited.add(item)

        attribute_set = item.get_attribute_set(identifier, True)
        old_value = attribute_set.get_cache(count_name, 0)
        attribute_set.set_cache(count_name, old_value + delta)

        for subscriber in item.subscriber_items:
            CountAttribute.__recursive_modify_count(subscriber, identifier, count_name, delta, visited)
