"""
Copyright (C) 2015 Analog Devices, Inc.
Author: Paul Cercueil <paul.cercueil@analog.com>

This program is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License
as published by the Free Software Foundation; either version 2
of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
"""

import iio

class iio_info:
  def __init__(self, context):
    self.context = context

  def print_info(self, verbose):
    self._context_info(verbose)

  def _context_info(self, verbose):
    print("IIO context created: " + self.context.name)
    print("Backend version: %u.%u (git tag: %s" % self.context.version)
    print("Backend description string: " + self.context.description)

    if len(self.context.attrs) > 0:
      print("IIO context has %u attributes: " % len(self.context.attrs))

    for attr, value in self.context.attrs.items():
      print("\t" + attr + ": " + value)

    print("IIO context has %u devices:" % len(self.context.devices))

    for dev in self.context.devices:
      self._device_info(dev, verbose)

  def _device_info(self, dev, verbose):
    print("\t" + dev.id + ": " + dev.name)

    if dev is iio.Trigger:
      print("Found trigger! Rate: %u HZ" % dev.frequency)

    print("\t\t%u channels found: " % len(dev.channels))
    for channel in dev.channels:
      self._channel_info(channel, verbose)

    if verbose:
      if len(dev.attrs) > 0:
        print("\t\t%u device-specific attributes found: " % len(dev.attrs))
        for device_attr in dev.attrs:
          self._device_attribute_info(dev, device_attr)

      if len(dev.debug_attrs) > 0:
        print("\t\t%u debug attributes found: " % len(dev.debug_attrs))
        for debug_attr in dev.debug_attrs:
          self._device_debug_attribute_info(dev, debug_attr)

  def _channel_info(self, channel, verbose):
    print("\t\t\t%s: %s (%s)" % (channel.id, channel.name or "", "output" if channel.output else "input"))
    if verbose:
      if len(channel.attrs) > 0:
        print("\t\t\t%u channel-specific attributes found: " % len(channel.attrs))
        for channel_attr in channel.attrs:
          self._channel_attribute_info(channel, channel_attr)

  @staticmethod
  def _channel_attribute_info(channel, channel_attr):
    try:
      print("\t\t\t\t" + channel_attr + ", value: " + channel.attrs[channel_attr].value)
    except OSError as err:
      print("Unable to read " + channel_attr + ": " + err.strerror)

  @staticmethod
  def _device_attribute_info(dev, device_attr):
    try:
      print("\t\t\t" + device_attr + ", value: " + dev.attrs[device_attr].value)
    except OSError as err:
      print("Unable to read " + device_attr + ": " + err.strerror)

  @staticmethod
  def _device_debug_attribute_info(dev, debug_attr):
    try:
      print("\t\t\t" + debug_attr + ", value: " + dev.debug_attrs[debug_attr].value)
    except OSError as err:
      print("Unable to read " + debug_attr + ": " + err.strerror)
