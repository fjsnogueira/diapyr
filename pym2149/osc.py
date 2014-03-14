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

from __future__ import division
import lfsr, numpy as np, itertools, math
from nod import BufNode
from dac import leveltoamp, amptolevel

class Values:

  def __init__(self, dtype, g, loop = 0):
    self.buf = np.fromiter(g, dtype)
    self.loop = loop

class OscNode(BufNode):

  def __init__(self, dtype, periodreg):
    BufNode.__init__(self, dtype)
    self.reset()
    self.periodreg = periodreg

  def reset(self):
    self.valueindex = 0
    self.progress = self.scaleofstep * 0xffff # Matching biggest possible 16-bit stepsize.

  def getvalue(self, n = 1):
    self.warp(n - 1)
    self.lastvalue = self.values.buf[self.valueindex]
    self.warp(1)
    return self.lastvalue

  def warp(self, n):
    self.valueindex += n
    size = self.values.buf.shape[0]
    while self.valueindex >= size:
      self.valueindex = self.values.loop + self.valueindex - size

  def prolog(self):
    # If progress beats the new stepsize, we terminate right away:
    cursor = min(self.block.framecount, max(0, self.stepsize - self.progress))
    cursor and self.blockbuf.fillpart(0, cursor, self.lastvalue)
    self.progress = min(self.progress + cursor, self.stepsize)
    return cursor

  def common(self, cursor):
    fullsteps = (self.block.framecount - cursor) // self.stepsize
    if self.blockbuf.putringops(self.values.buf, self.valueindex, fullsteps) * self.stepsize < fullsteps:
      for i in xrange(self.stepsize):
        self.blockbuf.putring(cursor + i, self.stepsize, self.values.buf, self.valueindex, fullsteps)
      self.getvalue(fullsteps)
      cursor += fullsteps * self.stepsize
    else:
      for _ in xrange(fullsteps):
        self.blockbuf.fillpart(cursor, cursor + self.stepsize, self.getvalue())
        cursor += self.stepsize
    if cursor < self.block.framecount:
      self.blockbuf.fillpart(cursor, self.block.framecount, self.getvalue())
      self.progress = self.block.framecount - cursor

class ToneDiff(BufNode):

  def __init__(self, scale, periodreg):
    BufNode.__init__(self, self.bindiffdtype)
    self.scaleofstep = scale * 2 // 2 # Normally half of 16.
    self.progress = self.scaleofstep * 0xffff # Matching biggest possible 16-bit stepsize.
    self.periodreg = periodreg
    self.last = -1

  def callimpl(self):
    self.blockbuf.fill(0)
    stepsize = self.scaleofstep * self.periodreg.value
    # If progress beats the new stepsize, we terminate right away:
    stepindex = max(0, stepsize - self.progress)
    if stepindex >= self.block.framecount:
      # Next step of waveform is beyond this block:
      if self.block.framecount: # TODO: This is dumb.
        self.blockbuf.addtofirst((self.last + 1) // 2)
        self.progress += self.block.framecount
      return
    periodsize = stepsize * 2
    self.blockbuf.putstrided(stepindex, periodsize, -self.last)
    self.blockbuf.putstrided(stepindex + stepsize, periodsize, self.last)
    self.blockbuf.addtofirst((self.last + 1) // 2) # Add last value of previous integral.
    self.progress = stepsize - (stepindex - self.block.framecount) % stepsize
    if ((self.block.framecount - stepindex + stepsize - 1) // stepsize) & 1:
      self.last = -self.last

class ToneOsc(BufNode):

  def __init__(self, scale, periodreg):
    BufNode.__init__(self, self.binarydtype)
    self.diff = ToneDiff(scale, periodreg)

  def callimpl(self):
    self.blockbuf.integrate(self.chain(self.diff))

class NoiseOsc(OscNode):

  values = Values(BufNode.binarydtype, lfsr.Lfsr(*lfsr.ym2149nzdegrees))

  def __init__(self, scale, periodreg):
    self.scaleofstep = scale * 2 # This results in authentic spectrum, see qnoispec.
    OscNode.__init__(self, BufNode.binarydtype, periodreg)
    self.stepsize = self.progress

  def callimpl(self):
    cursor = self.prolog()
    if cursor < self.block.framecount:
      self.progress = self.stepsize = self.scaleofstep * self.periodreg.value
      self.common(cursor)

def cycle(v, minsize): # Unlike itertools version, we assume v can be iterated more than once.
  for _ in xrange((minsize + len(v) - 1) // len(v)):
    for x in v:
      yield x

def sinevalues(steps): # Like saw but unlike triangular, we use steps for a full wave.
  levels = []
  minamp = leveltoamp(0)
  for i in xrange(steps):
    amp = minamp + (1 - minamp) * (math.sin(2 * math.pi * i / steps) + 1) / 2
    levels.append(round(amptolevel(amp)))
  return Values(BufNode.zto255dtype, cycle(levels, 1000))

class EnvOsc(OscNode):

  steps = 32
  values0c = Values(BufNode.zto255dtype, cycle(range(steps), 1000))
  values08 = Values(BufNode.zto255dtype, cycle(range(steps - 1, -1, -1), 1000))
  values0e = Values(BufNode.zto255dtype, cycle(range(steps) + range(steps - 1, -1, -1), 1000))
  values0a = Values(BufNode.zto255dtype, cycle(range(steps - 1, -1, -1) + range(steps), 1000))
  values0f = Values(BufNode.zto255dtype, itertools.chain(xrange(steps), itertools.repeat(0, 1000)), steps)
  values0d = Values(BufNode.zto255dtype, itertools.chain(xrange(steps), itertools.repeat(steps - 1, 1000)), steps)
  values0b = Values(BufNode.zto255dtype, itertools.chain(xrange(steps - 1, -1, -1), itertools.repeat(steps - 1, 1000)), steps)
  values09 = Values(BufNode.zto255dtype, itertools.chain(xrange(steps - 1, -1, -1), itertools.repeat(0, 1000)), steps)
  values10 = sinevalues(steps)

  def __init__(self, scale, periodreg, shapereg):
    self.scaleofstep = scale * 32 // self.steps
    OscNode.__init__(self, BufNode.zto255dtype, periodreg)
    self.shapeversion = None
    self.shapereg = shapereg

  def callimpl(self):
    if self.shapeversion != self.shapereg.version:
      shape = self.shapereg.value
      if shape == (shape & 0x07):
        shape = (0x09, 0x0f)[bool(shape & 0x04)]
      self.values = getattr(self, "values%02x" % shape)
      self.shapeversion = self.shapereg.version
      self.reset()
    self.stepsize = self.scaleofstep * self.periodreg.value
    cursor = self.prolog()
    if cursor < self.block.framecount:
      self.common(cursor)
