#
# Copyright (c) 2019 Red Hat, Inc.
#
# This file is part of nmstate
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 2.1 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
#

from contextlib import contextmanager

from libnmstate import nm
from libnmstate import schema
from libnmstate.schema import Interface

from .testlib import mainloop_run


BOND0 = 'bondtest0'


def test_create_and_remove_bond(eth1_up):
    bond_options = {
        schema.Bond.MODE: schema.BondMode.ROUND_ROBIN,
        'miimon': '140',
    }

    with _bond_interface(BOND0, bond_options):
        bond_current_state = _get_bond_current_state(BOND0)

        bond_desired_state = {
            schema.Bond.SLAVES: [],
            schema.Bond.OPTIONS_SUBTREE: bond_options,
        }
        assert bond_desired_state == bond_current_state

    assert not _get_bond_current_state(BOND0)


def test_bond_with_a_slave(eth1_up):
    bond_options = {schema.Bond.MODE: schema.BondMode.ROUND_ROBIN}

    with _bond_interface(BOND0, bond_options):
        nic_name = eth1_up[Interface.KEY][0][Interface.NAME]
        _attach_slave_to_bond(BOND0, nic_name)

        bond_current_state = _get_bond_current_state(BOND0)

        bond_desired_state = {
            schema.Bond.SLAVES: [nic_name],
            schema.Bond.OPTIONS_SUBTREE: bond_options,
        }
        assert bond_desired_state == bond_current_state

    assert not _get_bond_current_state(BOND0)


@contextmanager
def _bond_interface(name, options):
    try:
        _create_bond(name, options)
        yield
    finally:
        _delete_bond(name)


def _get_bond_current_state(name):
    nm.nmclient.client(refresh=True)
    nmdev = nm.device.get_device_by_name(name)
    nm_bond_info = nm.bond.get_bond_info(nmdev) if nmdev else {}
    return _convert_slaves_devices_to_iface_names(nm_bond_info)


@mainloop_run
def _create_bond(name, options):
    con_setting = nm.connection.ConnectionSetting()
    con_setting.create(
        con_name=name,
        iface_name=name,
        iface_type=nm.nmclient.NM.SETTING_BOND_SETTING_NAME,
    )
    bond_setting = nm.bond.create_setting(options)
    ipv4_setting = nm.ipv4.create_setting({}, None)
    ipv6_setting = nm.ipv6.create_setting({}, None)

    con_profile = nm.connection.ConnectionProfile()
    con_profile.create(
        (con_setting.setting, bond_setting, ipv4_setting, ipv6_setting)
    )
    con_profile.add(save_to_disk=False)
    nm.device.activate(connection_id=name)


@mainloop_run
def _delete_bond(devname):
    nmdev = nm.device.get_device_by_name(devname)
    nm.device.deactivate(nmdev)
    nm.device.delete(nmdev)


@mainloop_run
def _attach_slave_to_bond(bond, slave):
    slave_nmdev = nm.device.get_device_by_name(slave)
    curr_slave_con_profile = nm.connection.ConnectionProfile()
    curr_slave_con_profile.import_by_device(slave_nmdev)

    slave_con_profile = nm.connection.ConnectionProfile()
    slave_settings = [_create_connection_setting(bond, curr_slave_con_profile)]
    slave_con_profile.create(slave_settings)

    curr_slave_con_profile.update(slave_con_profile)
    curr_slave_con_profile.commit(nmdev=slave_nmdev)
    nm.device.activate(connection_id=slave)


def _create_connection_setting(bond, port_con_profile):
    con_setting = nm.connection.ConnectionSetting()
    con_setting.import_by_profile(port_con_profile)
    con_setting.set_master(bond, 'bond')

    return con_setting.setting


def _convert_slaves_devices_to_iface_names(info):
    if info:
        info['slaves'] = [slave.props.interface for slave in info['slaves']]
    return info
