# Copyright 2014 Andrzej Cichocki

# This file is part of pym2149.
#
# pym2149 is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# pym2149 is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with pym2149.  If not, see <http://www.gnu.org/licenses/>.

from buf import MasterBuf, NullBuf
import numpy as np

class Block:

  def __init__(self, framecount):
    self.framecount = framecount

  def __repr__(self):
    return "%s(%r)" % (self.__class__.__name__, self.framecount)

class Node:

  def __init__(self):
    self.block = None

  def call(self, block):
    return self(block, False)

  def __call__(self, block, masked):
    if self.block != block:
      self.block = block
      self.masked = masked
      self.result = self.callimpl()
    return self.result

  def callimpl(self):
    raise Exception('Implement me!')

  def chain(self, node):
    return node(self.block, self.masked)

class Container(Node):

  def __init__(self, nodes):
    Node.__init__(self)
    self.nodes = nodes

  def callimpl(self):
    return [self.chain(node) for node in self.nodes]

class BufNode(Node):

  zto255dtype = binarydtype = np.uint8 # Slightly faster than plain old int.
  zto127diffdtype = bindiffdtype = np.int8 # Suitable for derivative of [0, 127].
  floatdtype = np.float32 # Effectively about 24 bits.

  def __init__(self, dtype, channels = 1):
    Node.__init__(self)
    masterbuf = MasterBuf(dtype)
    callimpl = self.callimpl
    def callimploverride():
      if self.masked:
        self.blockbuf = NullBuf
      else:
        self.blockbuf = masterbuf.ensureandcrop(self.block.framecount * channels)
      resultornone = callimpl()
      if resultornone is not None:
        return resultornone
      return self.blockbuf
    self.callimpl = callimploverride
    self.dtype = dtype
