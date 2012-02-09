"""
A set of method which facilitate conversiton to and from
signed, unsigned and complex format number representations
"""

from math import *
import numpy as np

## A method to convert an integer into a bit string
def bit_string(val, width):
    bitstring = ''
    for i in range(width):
        bitstring += str((val & (1<<((width-1)-i)))>>((width-1)-i))
    return bitstring

## A method to convert unsigned integer to signed integer

def uint2int(uints, bitwidth):
    max_pos = 2**(bitwidth-1) -1
    mask = 2**bitwidth - 1
    neg_top_bit = 2**(bitwidth-1)

    is_negative = (uints&(1<<(bitwidth-1)))>>(bitwidth-1)
    
    ints = (-neg_top_bit*is_negative + (uints&(2**(bitwidth-1)-1)))

    return ints

## A method to convert a "CASPER format" complex number structure in a
## [real, imag] vector

def uint2cplx(uint,bitwidth):

    r_i_bitwidth = bitwidth
    mask = 2**(r_i_bitwidth)-1

    #real part
    real = uint2int(((uint & (mask << r_i_bitwidth)) >> r_i_bitwidth), r_i_bitwidth)

    #imag part
    imag = uint2int((uint & mask), r_i_bitwidth)

    #return complex vector

    return real + 1j*imag

## A method to calculate the power of a signal from the "CASPER format" unsigned
## complex form
def cplx2pow(cplx):
    power = np.real(cplx)**2 + np.imag(cplx)**2
    return power

def uint2pow(uint, bitwidth):
	return cplx2pow(uint2cplx(uint,bitwidth))

