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


class NotifyObservers(INotificationBehaviorInterface):
    """Notify observer items with a given attribute.

    When an item set the attribute to True, all item subscribing it will also set the attribute to true.
    """

    def __init__(self, attribute_name: str = 'activate'):
        """
        :param attribute_name: value type of this attribute should be bool
        """
        self.__attribute_name = attribute_name

    def get_attribute(self, handle, attribute_name: str):
        if attribute_name == self.__attribute_name:
            attribute_set = handle.attribute_set
            return attribute_set.attribute_dict.get(self.__attribute_name, False) or \
                attribute_set.inherited_attribute_dict.get(self.__attribute_name, False)
        else:
            raise NameError()

    def set_attribute(self, handle, attribute_name: str, attribute_value: bool):
        if attribute_name == self.__attribute_name:
            check_type(attribute_value, bool)
            self.__recursive_set_attribute(handle.attribute_set, handle.item, attribute_value, handle.identifier)
        else:
            raise NameError()

    def __recursive_set_attribute(self, attribute_set, item, attribute_value, identifier):
        # update self
        old_value = attribute_set.attribute_dict.get(self.__attribute_name, None)
        if old_value == attribute_value:
            return  # value not changed, no need to do anything

        attribute_set.attribute_dict[self.__attribute_name] = attribute_value

        # update observers
        inherited_value = attribute_set.inherited_attribute_dict.get(self.__attribute_name, False)
        old_gathered_value = old_value or inherited_value
        if old_gathered_value == attribute_value:
            return  # result not changed, no need to notify observer

        for i in item.observer_items:
            self.__recursive_set_attribute(i.get_attribute_set(identifier, True), i, attribute_value or inherited_value,
                                           identifier)
