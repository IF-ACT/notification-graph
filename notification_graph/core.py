from __future__ import annotations
from typing import Callable, Any, Dict, Generator, Set, Optional, Union
from .notification_behaviors import INotificationBehaviorInterface


class NotificationType(object):
    def __init__(self, type_identifier, behavior: INotificationBehaviorInterface, **default_attributes):
        assert isinstance(behavior, INotificationBehaviorInterface), behavior
        self.__identifier = type_identifier
        self.__behavior = behavior
        self.__default_attributes = default_attributes

    @property
    def behavior(self):
        return self.__behavior

    @property
    def identifier(self):
        return self.__identifier

    @property
    def default_attributes(self):
        return self.__default_attributes

    def __repr__(self):
        return f'<notification type {repr(self.__identifier)}>'


class NotificationAttributeSet(object):
    def __init__(self, attributes: Dict[str, Any]):
        self.attribute_dict = attributes
        '''Attributes owned by this item, should only be set by behaviors on same item.'''

        self.inherited_attribute_dict: Dict[str, Any] = {}
        '''Attributes inherited from other items, can be set by any behaviors.'''


class NotificationAttributeSetHandle(object):

    def __init__(self, attribute_set: NotificationAttributeSet, behavior: INotificationBehaviorInterface,
                 notification_item: NotificationItem, type_identifier):
        self._attribute_set = attribute_set
        self._behavior = behavior
        self._item = notification_item
        self._identifier = type_identifier

    @property
    def attribute_set(self):
        return self._attribute_set

    @property
    def item(self):
        return self._item

    @property
    def identifier(self):
        return self._identifier

    def get_attribute(self, attribute_name: str):
        """Get value of an attribute

        :param attribute_name: name of the attribute that specified when creating a behavior
        :return: value of the attribute
        :raise AttributeError:
        """
        try:
            return self._behavior.get_attribute(self, attribute_name)
        except NameError:
            raise AttributeError(f'can\'t access attribute {repr(attribute_name)}')

    def set_attribute(self, attribute_name: str, value):
        """Set value of an attribute

        :param attribute_name: name of the attribute that specified when creating a behavior
        :param value: value of the attribute
        :raise AttributeError:
        """
        try:
            self._behavior.set_attribute(self, attribute_name, value)
        except NameError:
            raise AttributeError(f'can\'t set attribute {repr(attribute_name)}')


class NotificationItem(object):

    def __init__(self):
        self.__graph: Optional[NotificationGraph] = None
        self.__notification_behaviors: Dict[Any, INotificationBehaviorInterface] = {}
        self.__notification_attributes: Dict[Any, NotificationAttributeSet] = {}
        self.__subscribe_set: Set[NotificationItem] = set()
        self.__observer_set: Set[NotificationItem] = set()

    @property
    def graph(self):
        return self.__graph

    @property
    def subscribed_items(self):
        for item in self.__subscribe_set:
            yield item

    @property
    def observer_items(self):
        for item in self.__observer_set:
            yield item

    def subscribe(self, item: NotificationItem, check_circular_subscription=True):
        """Subscribe another notification item, typically when the subscribed item does some change,
        self will receive a signore.

        :param item: another notification item in same graph
        :param check_circular_subscription: perform circular subscription check, set it to False if you
        are in confidence the operation won't cause circular subscription.
        """
        assert self is not item, 'can\'t subscribe self'
        self.__subscribe_set.add(item)
        item.__observer_set.add(self)

        if check_circular_subscription:
            try:
                self.walk_through()
            except AssertionError as e:
                self.__subscribe_set.remove(item)
                item.__observer_set.remove(self)
                raise e

        NotificationGraph.on_connect(self, item)

    def unsubscribe(self, item: NotificationItem):
        """TODO: Not safe yet, may cause graph split into two pieces

        :param item: another notification item in same graph
        :raise KeyError: not subscribed that item yet
        """
        try:
            self.__subscribe_set.remove(item)
        except KeyError:
            raise KeyError(f'{repr(self)} has not subscribed {repr(item)}')
        item.__observer_set.remove(self)

    def add_notification(self, notification_type: NotificationType, **attributes):
        """Add a new notification type to this item.

        :raise KeyError: notification type already exist
        """
        if notification_type in self:
            raise KeyError(f'{notification_type} already exist in this item')
        for k, v in notification_type.default_attributes.items():
            attributes.setdefault(k, v.__deepcopy__())
        self.__notification_behaviors[notification_type.identifier] = notification_type.behavior
        self.__notification_attributes[notification_type.identifier] = NotificationAttributeSet(attributes)

    def has_subscription(self, item: NotificationItem, find_indirect=False):
        """Returns True if self subscribed that item.

        :param item: item to search
        :param find_indirect: True to find recursively, False to find only direct subscriptions
        """
        if item is self:
            return False

        if item in self.__subscribe_set:
            return True
        elif find_indirect and self.__subscribe_set:
            return any(subscribed_item.has_subscription(item, True) for subscribed_item in self.__subscribe_set)
        else:
            return False

    def walk_through(self, upstream=False, assertion: Callable[[NotificationItem], bool] = lambda _: True,
                     terminate=True) -> Generator[NotificationItem]:
        """Walks through items recursively

        :param upstream: True to walk through upstream observer items, False to walk through downstream subscribed items
        :param assertion: stops when assertion returns false
        :param terminate: True to return when stopped, False to skip subtree items when stopped and continue
        """
        for item in self.__observer_set if upstream else self.__subscribe_set:
            if not assertion(item):
                if terminate:
                    break
                else:
                    continue
            yield item
            for recursive_item in item.walk_through(upstream, assertion, terminate):
                assert recursive_item is not self, 'circular subscription detected'
                yield recursive_item

    def get_attribute_set(self, notification_type, create_if_not_exist=False):
        """Raw access to attribute sets

        :returns: None if not exist
        """
        identifier = self.__get_identifier(notification_type)
        attribute_set = self.__notification_attributes.get(identifier, None)
        if attribute_set is None and create_if_not_exist:
            attribute_set = NotificationAttributeSet({})
            self.__notification_attributes[identifier] = attribute_set

        return attribute_set

    def _set_graph(self, graph: NotificationGraph):
        self.__graph = graph

    @staticmethod
    def __get_identifier(notification_type):
        return notification_type.identifier if isinstance(notification_type, NotificationType) else notification_type

    def __contains__(self, item):
        return self.__get_identifier(item) in self.__notification_behaviors

    def __getitem__(self, item):
        identifier = self.__get_identifier(item)
        behavior = self.__notification_behaviors.get(identifier, None)
        if behavior is None:
            raise KeyError(f'{repr(identifier)} is not accessible')
        return NotificationAttributeSetHandle(self.__notification_attributes[identifier], behavior, self, identifier)


# noinspection PyProtectedMember
class NotificationGraph(object):
    """Graphs can have very short lifetime, never keep instance of this class.
    Use all instances as temporary variables."""

    def __init__(self):
        self.__items: Set[NotificationItem] = set()

    @staticmethod
    def create(*args: Union[NotificationItem, NotificationGraph]):
        """Create a new graph from items or graphs"""
        graph = NotificationGraph()
        for arg in args:
            if isinstance(arg, NotificationItem):
                assert arg.graph is None, f'can\'t create with item {repr(arg)}, it is already in graph {arg.graph}'
                graph.__add_item(arg)
            elif isinstance(arg, NotificationGraph):
                for item in arg.__items:
                    graph.__add_item(item)
                arg.__destroy()
            else:
                raise TypeError(f'unknown argument type {repr(arg.__class__)} at index {args.index(arg)}')
        return graph

    def __destroy(self):
        self.__items = None

    def __add_item(self, item: NotificationItem):
        self.__items.add(item)
        item._set_graph(self)

    @staticmethod
    def on_connect(item1: NotificationItem, item2: NotificationItem):
        graph1 = item1.graph
        graph2 = item2.graph
        if graph1 is None and graph2 is None:
            NotificationGraph.create(item1, item2)
        elif item1.graph is None:
            item2.graph.__add_item(item1)
        elif item2.graph is None:
            item1.graph.__add_item(item2)
        elif item1.graph is item2.graph:
            return
        else:
            NotificationGraph.create(graph1, graph2)
