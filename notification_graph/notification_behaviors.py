from .util import check_type

# only for typing hint
# noinspection PyUnreachableCode
if False:
    # noinspection PyUnresolvedReferences
    from .core import *


class INotificationBehaviorInterface:
    """Interface of all notification behaviors."""

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

    def post_subscribe(self, subscriber_item, notifier_item):
        """Called after a new subscription established in the graph.

        :param subscriber_item:
        :type subscriber_item: NotificationItem
        :param notifier_item:
        :type notifier_item: NotificationItem
        """

    def pre_unsubscribe(self, subscriber_item, notifier_item):
        """Called before subscriber item unsubscribes an item.

        :param subscriber_item:
        :type subscriber_item: NotificationItem
        :param notifier_item:
        :type notifier_item: NotificationItem
        """


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

    def post_subscribe(self, subscriber_item, notifier_item):
        for identifier in subscriber_item.graph.get_related_identifiers(self):
            attribute_set = notifier_item.get_attribute_set(identifier)
            if attribute_set is None:
                continue
            if self.__get_gathered_value(attribute_set):
                self.__recursive_set_true(subscriber_item, identifier)

    def pre_unsubscribe(self, subscriber_item, notifier_item):
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
