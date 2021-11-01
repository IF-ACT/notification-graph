from __future__ import annotations
from typing import Callable, Any, Dict, Generator, Set, Optional, Tuple, Iterable
from .notification_behaviors import INotificationBehaviorInterface
from .util import merge_dict_set_values, EGraphCondition


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

    def has_attribute(self, attribute):
        return attribute in self.__attribute_dict

    def get_cache(self, attribute: str, default=None):
        return self.__inherited_attribute_dict.get(attribute, default)

    def set_cache(self, attribute: str, value):
        self.__inherited_attribute_dict[attribute] = value

    def has_cache(self, attribute: str):
        return attribute in self.__inherited_attribute_dict


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
    def is_single(self):
        return self.__graph is None

    @property
    def is_head(self):
        """True if this node subscribes all other nodes in its graph."""
        return self.__graph is None or self.__graph.head is self

    @property
    def is_head_of_tree(self):
        """True if this node is head of a tree."""
        return self.__graph is None or (self.__graph.is_tree and self.graph.head is self)

    @property
    def _notification_behaviors(self):
        return self.__notification_behaviors

    def is_in_same_graph(self, other: NotificationItem):
        """True if other is in the same graph with self."""
        return self.__graph is not None and self.graph is other.__graph

    def subscribe(self, item: NotificationItem, check_circular_subscription=True):
        """Subscribe another notification item, typically when the notifier item does some change,
        self will receive a signore.

        :param item: another notification item in same graph
        :param check_circular_subscription: perform circular subscription check, set it to False if you
            are in confidence the operation won't cause circular subscription.
        """
        assert self is not item, 'can\'t subscribe self'
        info = NotificationGraph.do_pre_subscribe(self, item, check_circular_subscription)
        item.__subscriber_set.add(self)
        self.__notifier_set.add(item)
        NotificationGraph.do_post_subscribe(self, item, info)

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
        if item is self or not self.is_in_same_graph(item):
            return False

        if item in self.__notifier_set:
            return True
        elif find_indirect and self.__notifier_set:
            return any(item in notifier_item.__notifier_set for notifier_item in self.walk_through())
        else:
            return False

    def walk_through(self, upstream=False, assertion: Callable[[NotificationItem], bool] = lambda _: True,
                     terminate=True) -> Generator[NotificationItem]:
        """Walks through items recursively

        :param upstream: True to walk through upstream subscriber items, False to walk through downstream notifier items
        :param assertion: stops when assertion returns false
        :param terminate: True to return when stopped, False to skip subtree items when stopped and continue
        """
        if self.__graph is None or self.__graph.is_tree:
            visited = None  # for a tree, no need to cache visited items
        else:
            visited = set()

        for item in self.__subscriber_set if upstream else self.__notifier_set:
            if visited is not None and item in visited:
                continue
            if not assertion(item):
                if terminate:
                    break
                else:
                    continue
            yield item
            if visited is not None:
                visited.add(item)
            for recursive_item in item.walk_through(upstream, assertion, terminate):
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

        self.__head: Optional[NotificationItem] = None
        self.__is_tree = True
        self.__graph_head_count = 0

        self._destroyed = False

    @property
    def is_tree(self) -> bool:
        """True if this graph is actually a tree."""
        return self.__is_tree

    @property
    def head(self):
        """Head here means the item that subscribes all other items in the graph.
        A tree always has head, a graph may or may not has head."""
        return self.__head

    def notify_pre_set_attribute(self, handle: NotificationAttributeSetHandle, attribute_name: str, attribute_value):
        behavior_set = self.__interest_attributes.get((handle.identifier, attribute_name), None)
        if behavior_set is None:
            return

        for behavior in behavior_set:
            behavior.set_attribute(handle, attribute_name, attribute_value)

    @staticmethod
    def do_pre_subscribe(subscriber: NotificationItem, notifier: NotificationItem,
                         check_circular_subscription: bool):
        """Invoked before subscription, returns information for do_post_subscribe() to use."""
        from itertools import chain

        condition = EGraphCondition.get_condition(subscriber.graph, notifier.graph)
        behaviors: Dict[INotificationBehaviorInterface, set]
        if condition == EGraphCondition.BothSingle:
            behaviors = {}
            NotificationGraph.__add_behaviors(behaviors,
                                              chain(subscriber._notification_behaviors.items(),
                                                    notifier._notification_behaviors.items()))
        elif condition == EGraphCondition.NotifierSingle:
            behaviors = subscriber.graph.__behaviors
            NotificationGraph.__add_behaviors(behaviors, notifier._notification_behaviors.items())
        elif condition == EGraphCondition.SubscriberSingle:
            behaviors = notifier.graph.__behaviors
            NotificationGraph.__add_behaviors(behaviors, subscriber._notification_behaviors.items())
        else:
            # subscription in same graph may cause circle
            if check_circular_subscription:
                for item in notifier.walk_through():
                    assert item is not subscriber, 'circular subscription detected'

            behaviors = subscriber.graph.__behaviors
            merge_dict_set_values(behaviors, notifier.graph.__behaviors)

        for behavior, identifiers in behaviors.items():
            for identifier in identifiers:
                behavior.pre_subscribe(subscriber, notifier, identifier)

        return condition, behaviors

    @staticmethod
    def __add_behaviors(behavior_dict: Dict[INotificationBehaviorInterface, set],
                        iter_behaviors: Iterable[Tuple[Any, INotificationBehaviorInterface]]):
        for identifier, behavior in iter_behaviors:
            id_set = behavior_dict.setdefault(behavior, set())
            id_set.add(identifier)

    @staticmethod
    def do_post_subscribe(subscriber: NotificationItem, notifier: NotificationItem,
                          pre_subscribe_info: Tuple[int, Dict[INotificationBehaviorInterface, set]]):
        # deal with tree and head attributes
        is_tree = NotificationGraph.is_tree_after_connect(subscriber, notifier)
        graph_head_count: int
        head: Optional[NotificationItem] = None
        if is_tree:
            head = subscriber if subscriber.is_single else subscriber.graph.head
            graph_head_count = 1
        elif subscriber.is_in_same_graph(notifier):
            graph_head_count = subscriber.graph.__graph_head_count
            if not notifier.subscriber_items:
                assert graph_head_count > 1, f'head is subscribed, circular subscription detected'
                graph_head_count -= 1
                if graph_head_count == 1:
                    # find head if only remains 1 graph head
                    if not subscriber.subscriber_items:
                        head = subscriber
                    else:
                        for item in subscriber.walk_through(True):
                            if not item.subscriber_items:
                                head = item
                                break
                    assert head
            else:
                head = subscriber.graph.head
        elif notifier.is_head:
            head = subscriber.graph.head
            graph_head_count = subscriber.graph.__graph_head_count
        else:
            head = None
            graph_head_count = subscriber.graph.__graph_head_count + notifier.graph.__graph_head_count
            if not notifier.subscriber_items:
                graph_head_count -= 1

        # merge or create graph
        condition, behaviors = pre_subscribe_info
        if condition == EGraphCondition.BothSingle:
            g = NotificationGraph()
            g.__items = {subscriber, notifier}
            for item in g.__items:
                g.__collect_interest(item)
                item._set_graph(g)
        elif condition == EGraphCondition.SubscriberSingle:
            g = notifier.graph
            g.__items.add(subscriber)
            g.__collect_interest(subscriber)
            subscriber._set_graph(g)
        elif condition == EGraphCondition.NotifierSingle:
            g = subscriber.graph
            g.__items.add(notifier)
            g.__collect_interest(notifier)
            notifier._set_graph(g)
        else:
            g = subscriber.graph
            if not subscriber.is_in_same_graph(notifier):
                abandoned_graph = notifier.graph
                g.__items |= abandoned_graph.__items
                merge_dict_set_values(g.__interest_attributes, abandoned_graph.__interest_attributes)
                abandoned_graph.__replace_with(g)

        g.__behaviors = behaviors

        g.__is_tree = is_tree
        g.__graph_head_count = graph_head_count
        g.__head = head

    def notify_pre_unsubscribe(self, subscriber: NotificationItem, notifier: NotificationItem):
        for behavior, related_identifiers in self.__behaviors.items():
            for identifier in related_identifiers:
                behavior.pre_unsubscribe(subscriber, notifier, identifier)

    def __collect_interest(self, item: NotificationItem):
        for identifier, behavior in item._notification_behaviors.items():
            for attribute in behavior.get_interested_attributes():
                behavior_set = self.__interest_attributes.setdefault((identifier, attribute), set())
                behavior_set.add(behavior)

    def __replace_with(self, graph: NotificationGraph):
        for item in self.__items:
            item._set_graph(graph)
        self.__destroy()

    def __destroy(self):
        del self.__items
        del self.__behaviors
        self._destroyed = True

    @staticmethod
    def is_tree_after_connect(subscriber: NotificationItem, notifier: NotificationItem):
        return (subscriber.is_single or subscriber.graph.is_tree) and \
               notifier.is_head_of_tree

    def debug_mermaid_graph(self, notification_type, *attributes: str, left_to_right=False):
        """Draw the tree with mermaid.

        Open the output of this function in a markdown viewer, e.g. typora, and you can see the graph image.
        """
        tab = '  '
        result = [
            f'{"Tree" if self.is_tree else "Graph"} for {repr(notification_type)} with {len(self)} items:\n\n'
            f'```mermaid\n'
            f'flowchart {"LR" if left_to_right else "TD"}\n']

        # mermaid syntax
        m_newline = '<br/>'
        m_star_f = '#starf;'
        m_star = '#star;'

        def sort_method(i):
            return id(i)

        sorted_items = list(self.__items)
        sorted_items.sort(key=sort_method)

        item_index = {}

        for index, item in enumerate(sorted_items):
            item_index[item] = index
            title = f'item {index}'
            attribute_set = item.get_attribute_set(notification_type)
            if attribute_set is None:
                content = '(empty)'
            else:
                content_lines = []
                for attribute in attributes:
                    attr_part = f'{m_star_f}{repr(attribute_set.get_attribute(attribute))}' \
                        if attribute_set.has_attribute(attribute) else ''
                    cache_part = f'{m_star}{repr(attribute_set.get_cache(attribute))}' \
                        if attribute_set.has_cache(attribute) else ''
                    combined = attr_part + (' ' if attr_part and cache_part else '') + cache_part
                    content_lines.append(f'{attribute}: {combined}')
                content = m_newline.join(content_lines)
            result.append(f'{tab}item_{index}(["{title}{m_newline}{content}"])\n')

        result.append('\n')

        current = {self.head} if self.head else {item for item in sorted_items if not item.subscriber_items}
        visited = set()
        while current:
            sorted_current = list(current)
            sorted_current.sort(key=sort_method)
            current.clear()
            for item in sorted_current:
                for notifier in item.notifier_items:
                    result.append(f'{tab}item_{item_index[item]} --> item_{item_index[notifier]}\n')
                    if notifier not in visited:
                        current.add(notifier)
            visited.union(sorted_current)

        result.append('```')
        return ''.join(result)

    def __getattribute__(self, item):
        if super(NotificationGraph, self).__getattribute__('_destroyed'):
            raise ValueError('this graph is already destroyed')
        return super(NotificationGraph, self).__getattribute__(item)

    def __len__(self):
        return len(self.__items)

    def __iter__(self):
        for item in self.__items:
            yield item
