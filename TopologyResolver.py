import logging

from SubnetTree import SubnetTree

from LoggingHelper import addrstr

class IterableSubnetTree(SubnetTree):
    """A thin (and ugly) wrapper around SubnetTree to provide a means to access
    all values in the tree, and to test if a specific key is in the tree."""
    def __init__(self):
        SubnetTree.__init__(self)
        self.keys = {}

    def __setitem__(self, key, value):
        SubnetTree.__setitem__(self, key, value)
        self.keys.__setitem__(key, value)

    def __delitem__(self, key):
        SubnetTree.__delitem__(self, key)
        self.keys.__delitem__(key)

    def has_exact(self, key):
        """Returns True if the specified key has been inserted in the tree."""
        return self.keys.has_key(key)

    def values(self):
        return self.keys.values()

class TopologyResolver:
    """Resolves destination addresses to the appropriate active topology."""
    def __init__(self):
        # Maps a destination IP address to an IterableSubnetTree object which
        # maps source addresses to Topology objects.
        self.i2t = {}

        # Maps destination MAC addresses to Topology objects.
        self.m2t = {}

    def register_topology(self, topo):
        """Registers a topology with the resolver."""
        if not topo.has_gateway():
            return # it is isolated from the real world

        for mac in topo.get_my_mac_addrs():
            try:
                self.m2t[mac].append(topo)
            except KeyError:
                self.m2t[mac] = [topo]

        for ip in topo.get_my_ip_addrs():
            # get the source filtering tree associated with the destination
            try:
                st = self.i2t[ip]
            except KeyError:
                st = IterableSubnetTree()
                self.i2t[ip] = st

            # register which sources this topo wants packets from
            for ps in topo.get_source_filters():
                if st.has_exact(ps):
                    # another topo has both this dst IP and the same source filter
                    st[ps].append(topo)
                else:
                    st[ps] = [topo]

    def unregister_topology(self, topo):
        """Unregisters a topology with the resolver."""
        if not topo.has_gateway():
            return # it is isolated from the real world

        for mac in topo.get_my_mac_addrs():
            try:
                topos = self.m2t[mac]
                try:
                    topos.remove(mac)
                    if not topos:
                        del self.m2t[mac]
                except ValueError:
                    logging.error('%s: missing topo in list for %s' % (topo, addrstr(mac)))
            except KeyError:
                logging.error('%s: missing topo list for %s' % (topo, addrstr(mac)))

        for ip in topo.get_my_ip_addrs():
            # get the source filtering tree associated with the destination
            try:
                st = self.i2t[ip]
            except KeyError:
                logging.error('%s: missing subnet tree for %s' % (topo, addrstr(ip)))
                continue

            # unregister which sources this topo wants packets from
            for ps in topo.get_source_filters():
                try:
                    topos = st[ps]
                    try:
                        topos.remove(topo) # remove this topology's registration
                        if not topos:
                            del st[ps]
                    except ValueError:
                        logging.error('%s: missing topology in source filter %s for %s' % (topo, ps, addrstr(ip)))
                except KeyError:
                    logging.error('%s: missing source filter %s for %s' % (topo, ps, addrstr(ip)))

    def resolve_ip(self, dst_ip, src_ip=None):
        """Resolves a src and dst IP address pair to a list of topologies to
        which the packet with this src and dst should be forwarded.  All
        parameters should be in network byte ordered byte strings.

        @param dst_ip_or_mac  The destination IP or MAC address.

        @param src_ip  The source IP this packet is from.  It may be omitted
                       when the source IP is not known (e.g., L2 traffic).

        @return An empty list is returned if no mapping exists.  Otherwise, the
                returned list is all topologies which should receive the packet.
        """
        try:
            st = self.i2t[dst_ip]
        except KeyError:
            return [] # no topology has this IP address

        # If there is no source IP, return all of the topologies which have this
        # destination address.
        if not src_ip:
            return st.values()

        # Figure out which topology is interested in packets from this source.
        try:
            return st[src_ip]
        except KeyError:
            return [] # nobody is interested in packets from this source

    def resolve_mac(self, dst_mac):
        """Resolves a dst MAC address to a list of topologies to which the
        packet to this dst should be forwarded."""
        try:
            return self.m2t[dst_mac]
        except KeyError:
            return [] # no topology has this MAC address