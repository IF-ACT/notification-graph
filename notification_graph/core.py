from __future__ import annotations
from typing import Callable, Any, Dict, Generator, Set, Optional, Union, Tuple
from .notification_behaviors import INotificationBehaviorInterface
from .util import merge_dict_set_values


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
        return f'<notification type {repr(self.__identifier)} with behavior {self.__behavior}>'


class NotificationAttributeSet(object):
    def __init__(self, attributes: Dict[str, Any]):
        self.__attribute_dict = attributes
        '''Attributes owned by this item, should only be set by behaviors on same item.'''

        self.__inherited_attribute_dict: Dict[str, Any] = {}
        '''Attributes inherited from other items, can be set by any behaviors.'''

    def get_attribute(self, attribute: str, default=None):
        return self.__attribute_dict.get(attribute, default)

    def set_attribute(self, attribute: str, value):
        self.__attribute_dict[attribute] = value

    def get_cache(self, attribute: str, default=None):
        return self.__inherited_attribute_dict.get(attribute, default)

    def set_cache(self, attribute: str, value):
        self.__inherited_attribute_dict[attribute] = value


class NotificationAttributeSetHandle(object):

    def __init__(self, attribute_set: NotificationAttributeSet, behavior: INotificationBehaviorInterface,
                 notification_item: NotificationItem, type_identifier):
        self.__attribute_set = attribute_set
        self.__behavior = behavior
        self.__item = notification_item
        self.__identifier = type_identifier

    @property
    def attribute_set(self):
        return self.__attribute_set

    @property
    def item(self):
        return self.__item

    @property
    def identifier(self):
        return self.__identifier

    def get_attribute(self, attribute_name: str):
        """Get value of an attribute

        :param attribute_name: name of the attribute that specified when creating a behavior
        :return: value of the attribute
        :raise AttributeError:
        """
        try:
            return self.__behavior.get_attribute(self, attribute_name)
        except NameError:
            raise AttributeError(f'can\'t access attribute {repr(attribute_name)}')

    def set_attribute(self, attribute_name: str, value):
        """Set value of an attribute

        :param attribute_name: name of the attribute that specified when creating a behavior
        :param value: value of the attribute
        :raise AttributeError:
        """
        graph = self.__item.graph
        if graph is not None:
            graph.notify_pre_set_attribute(self, attribute_name, value)
        try:
            self.__behavior.set_attribute(self, attribute_name, value)
        except NameError:
            raise AttributeError(f'can\'t set attribute {repr(attribute_name)}')


class NotificationItem(object):

    def __init__(self):
        self.__graph: Optional[NotificationGraph] = None
        self.__notification_behaviors: Dict[Any, INotificationBehaviorInterface] = {}
        self.__notification_attributes: Dict[Any, NotificationAttributeSet] = {}
        self.__notifier_set: Set[NotificationItem] = set()
        self.__subscriber_set: Set[NotificationItem] = set()

    @property
    def graph(self):
        """This value may be destroyed, do not keep instance of it, use it as temporary value instead"""
        return self.__graph

    @property
    def notifier_items(self):
        """Do not modify this property

        :return: items subscribed by self
        """
        return self.__notifier_set

    @property
    def subscriber_items(self):
        """Do not modify this property

        :return: items subscribing self
        """
        return self.__subscriber_set

    @property
    def _notification_behaviors(self):
        return self.__notification_behaviors

    def subscribe(self, item: NotificationItem, check_circular_subscription=True):
        """Subscribe another notification item, typically when the notifier item does some change,
        self will receive a signore.

        :param item: another notification item in same graph
        :param check_circular_subscription: perform circular subscription check, set it to False if you
            are in confidence the operation won't cause circular subscription.
        """
        assert self is not item, 'can\'t subscribe self'
        item.__subscriber_set.add(self)
        self.__notifier_set.add(item)

        if check_circular_subscription:
            try:
                for _ in self.walk_through():
                    pass
            except AssertionError as e:
                self.__notifier_set.remove(item)
                item.__subscriber_set.remove(self)
                raise e

        NotificationGraph.on_connect(self, item)
        self.graph.notify_post_subscribe(self, item)

    def unsubscribe(self, item: NotificationItem):
        """TODO: Not safe yet, may cause graph split into two pieces

        :param item: another notification item in same graph
        :raise KeyError: not notifier that item yet
        """
        if item not in self.__notifier_set:
            raise KeyError(f'{repr(self)} has not notifier {repr(item)}')
        self.graph.notify_pre_unsubscribe(self, item)
        self.__notifier_set.remove(item)
        item.__subscriber_set.remove(self)

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
        """Returns True if self notifier that item.

        :param item: item to search
        :param find_indirect: True to find recursively, False to find only direct subscriptions
        """
        if item is self:
            return False

        if item in self.__notifier_set:
            return True
        elif find_indirect and self.__notifier_set:
            return any(notifier_item.has_subscription(item, True) for notifier_item in self.__notifier_set)
        else:
            return False

    def walk_through(self, upstream=False, assertion: Callable[[NotificationItem], bool] = lambda _: True,
                     terminate=True) -> Generator[NotificationItem]:
        """Walks through items recursively

        :param upstream: True to walk through upstream subscriber items, False to walk through downstream notifier items
        :param assertion: stops when assertion returns false
        :param terminate: True to return when stopped, False to skip subtree items when stopped and continue
        """
        for item in self.__subscriber_set if upstream else self.__notifier_set:
            if not assertion(item):
                if terminate:
                    break
                else:
                    continue
            yield item
            for recursive_item in item.walk_through(upstream, assertion, terminate):
                assert recursive_item is not self, 'circular subscription detected'
                yield recursive_item

    def get_attribute(self, notification_type, attribute: str):
        """:raise KeyError, NameError:"""
        return self[notification_type].get_attribute(attribute)

    def set_attribute(self, notification_type, attribute: str, value):
        """:raise KeyError, NameError:"""
        self[notification_type].set_attribute(attribute, value)

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
    Use all instances as temporary variables.

    The graph is supposed to be a directed acyclic graph.
    """

    def __init__(self):
        self.__items: Set[NotificationItem] = set()
        self.__behaviors: Dict[INotificationBehaviorInterface, set] = {}
        '''Behaviors with their related identifiers in this graph.

        key: behavior,
        value: set of related identifiers'''

        self.__interest_attributes: Dict[Tuple[Any, str], Set[INotificationBehaviorInterface]] = {}
        '''When a behavior 'show interest' to an attribute, we register it here, and before every
        set attribute operation, we invoke set_attribute() on that behavior.

        key: (identifier, attribute name),
        value: set of behaviors'''

        self._destroyed = False

    def notify_pre_set_attribute(self, handle: NotificationAttributeSetHandle, attribute_name: str, attribute_value):
        behavior_set = self.__interest_attributes.get((handle.identifier, attribute_name), None)
        if behavior_set is None:
            return

        for behavior in behavior_set:
            behavior.set_attribute(handle, attribute_name, attribute_value)

    def notify_post_subscribe(self, subscriber: NotificationItem, notifier: NotificationItem):
        for behavior, related_identifiers in self.__behaviors.items():
            behavior.post_subscribe(subscriber, notifier, related_identifiers)

    def notify_pre_unsubscribe(self, subscriber: NotificationItem, notifier: NotificationItem):
        for behavior, related_identifiers in self.__behaviors.items():
            behavior.pre_unsubscribe(subscriber, notifier, related_identifiers)

    @staticmethod
    def create(*args: Union[NotificationItem, NotificationGraph]):
        """Create a new graph from items or graphs"""
        graph = NotificationGraph()
        for arg in args:
            if isinstance(arg, NotificationItem):
                item_graph = arg.graph
                assert item_graph is None or super(NotificationGraph, item_graph).__getattribute__('_destroyed'), \
                    f'can\'t create with item {repr(arg)}, it is already in graph {item_graph}'
                graph.__add_item(arg, True)

            elif isinstance(arg, NotificationGraph):
                for item in arg.__items:
                    graph.__add_item(item)
                merge_dict_set_values(graph.__behaviors, arg.__behaviors)
                merge_dict_set_values(graph.__interest_attributes, arg.__interest_attributes)
                arg.__destroy()

            else:
                raise TypeError(f'unknown argument type {repr(arg.__class__)} at index {args.index(arg)}')
        return graph

    def __destroy(self):
        del self.__items
        del self.__behaviors
        self._destroyed = True

    def __add_item(self, item: NotificationItem, register_behaviors=False):
        self.__items.add(item)
        item._set_graph(self)

        if register_behaviors:
            for identifier, behavior in item._notification_behaviors.items():
                # register behaviors
                id_set = self.__behaviors.setdefault(behavior, set())
                id_set.add(identifier)

                # register interests
                for attribute in behavior.get_interested_attributes():
                    behavior_set = self.__interest_attributes.setdefault((identifier, attribute), set())
                    behavior_set.add(behavior)

    @staticmethod
    def on_connect(subscriber: NotificationItem, notifier: NotificationItem):
        graph1 = subscriber.graph
        graph2 = notifier.graph
        if graph1 is None and graph2 is None:
            NotificationGraph.create(subscriber, notifier)
        elif subscriber.graph is None:
            notifier.graph.__add_item(subscriber, True)
        elif notifier.graph is None:
            subscriber.graph.__add_item(notifier, True)
        elif subscriber.graph is notifier.graph:
            pass
        else:
            NotificationGraph.create(graph1, graph2)

    def __getattribute__(self, item):
        if super(NotificationGraph, self).__getattribute__('_destroyed'):
            raise ValueError('this graph is already destroyed')
        return super(NotificationGraph, self).__getattribute__(item)
