#!/usr/bin/env python

import unittest, lfsr
from osc import *
from buf import *

class Reg:

  def __init__(self, value):
    self.value = value

class TestToneOsc(unittest.TestCase):

  def test_works(self):
    v = Buf().atleast(97)
    v[96] = 100
    ToneOsc(Reg(3))(v, 96)
    self.assertEqual([1] * 24, list(v[:24]))
    self.assertEqual([0] * 24, list(v[24:48]))
    self.assertEqual([1] * 24, list(v[48:72]))
    self.assertEqual([0] * 24, list(v[72:96]))
    self.assertEqual([100], list(v[96:]))

  def test_stopping(self):
    v = Buf().atleast(26)
    v[25] = 100
    ToneOsc(Reg(3))(v, 25)
    self.assertEqual([1] * 24, list(v[:24]))
    self.assertEqual([0], list(v[24:25]))
    self.assertEqual([100], list(v[25:]))

class TestNoiseOsc(unittest.TestCase):

  def test_works(self):
    n = 100
    v = Buf().atleast(48 * n)
    NoiseOsc(Reg(3))(v, len(v))
    u = lfsr.Lfsr(*lfsr.ym2149nzdegrees)
    for i in xrange(n):
      self.assertEqual([u()] * 48, list(v[i * 48:(i + 1) * 48]))

if __name__ == '__main__':
  unittest.main()
