#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Python wrapper around the C extension for the counts-in-cells
for 3-D real space. Corresponding C codes are in ``theory/vpf``
while the python wrapper is in :py:mod:`Corrfunc.theory.vpf`.
"""

from __future__ import (division, print_function, absolute_import,
                        unicode_literals)

__author__ = ('Manodeep Sinha')
__all__ = ('vpf', )


def vpf(rmax, nbins, nspheres, numpN, seed,
        X, Y, Z,
        verbose=False, periodic=True, boxsize=0.0,
        c_api_timer=False, isa='fastest'):
    """
    Function to compute the counts-in-cells on 3-D real-space points.

    Returns a numpy structured array containing the probability of a
    sphere of radius up to ``rmax`` containing [0, numpN-1] galaxies.

    Parameters
    -----------

    rmax: double
       Maximum radius of the sphere to place on the particles

    nbins: integer
       Number of bins in the counts-in-cells. Radius of first shell
       is rmax/nbins

    nspheres: integer (>= 0)
       Number of random spheres to place within the particle distribution.
       For a small number of spheres, the error is larger in the measured
       pN's.

    numpN: integer (>= 1)
       Governs how many unique pN's are to returned. If ``numpN`` is set to 1,
       then only the vpf (p0) is returned. For ``numpN=2``, p0 and p1 are
       returned.

       More explicitly, the columns in the results look like the following:

         ======   ==========================
         numpN    Columns in output
         ======   ==========================
            1      p0
            2      p0      p1
            3      p0      p1     p2
            4      p0      p1     p2     p3
         ======   ==========================

       and so on...(note that p0 is the vpf).

    seed: unsigned integer
       Random number seed for the underlying GSL random number generator. Used
       to draw centers of the spheres.

    X/Y/Z: arraytype, real (float/double)
       Particle positions in the 3 axes. Must be within [0, boxsize]
       and specified in the same units as ``rp_bins`` and boxsize. All
       3 arrays must be of the same floating-point type.

       Calculations will be done in the same precision as these arrays,
       i.e., calculations will be in floating point if XYZ are single
       precision arrays (C float type); or in double-precision if XYZ
       are double precision arrays (C double type).

    verbose: boolean (default false)
       Boolean flag to control output of informational messages

    periodic: boolean
        Boolean flag to indicate periodic boundary conditions.

    boxsize: double
        The side-length of the cube in the cosmological simulation.
        Present to facilitate exact calculations for periodic wrapping.
        If boxsize is not supplied, then the wrapping is done based on
        the maximum difference within each dimension of the X/Y/Z arrays.

    c_api_timer: boolean (default false)
       Boolean flag to measure actual time spent in the C libraries. Here
       to allow for benchmarking and scaling studies.

    isa: string (default ``fastest``)
       Controls the runtime dispatch for the instruction set to use. Possible
       options are: [``fastest``, ``avx``, ``sse42``, ``fallback``]

       Setting isa to ``fastest`` will pick the fastest available instruction
       set on the current computer. However, if you set ``isa`` to, say,
       ``avx`` and ``avx`` is not available on the computer, then the code will
       revert to using ``fallback`` (even though ``sse42`` might be available).

       Unless you are benchmarking the different instruction sets, you should
       always leave ``isa`` to the default value. And if you *are*
       benchmarking, then the string supplied here gets translated into an
       ``enum`` for the instruction set defined in ``utils/defs.h``.

    Returns
    --------

    results: Numpy structured array

       A numpy structured array containing [rmax, pN[numpN]] with ``nbins``
       elements. Each row contains the maximum radius of the sphere and the
       ``numpN`` elements in the ``pN`` array. Each element of this array
       contains the probability that a sphere of radius ``rmax`` contains
       *exactly* ``N`` galaxies. For example, pN[0] (p0, the void probibility
       function) is the probability that a sphere of radius ``rmax`` contains 0
       galaxies.

       if ``c_api_timer`` is set, then the return value is a tuple containing
       (results, api_time). ``api_time`` measures only the time spent within
       the C library and ignores all python overhead.

    Example
    --------

    >>> from __future__ import print_function
    >>> import numpy as np
    >>> from Corrfunc.theory.vpf import vpf
    >>> rmax = 10.0
    >>> nbins = 10
    >>> nspheres = 10000
    >>> numpN = 5
    >>> seed = -1
    >>> N = 100000
    >>> boxsize = 420.0
    >>> seed = 42
    >>> np.random.seed(seed)
    >>> X = np.random.uniform(0, boxsize, N)
    >>> Y = np.random.uniform(0, boxsize, N)
    >>> Z = np.random.uniform(0, boxsize, N)
    >>> results = vpf(rmax, nbins, nspheres, numpN, seed, X, Y, Z)
    >>> for r in results:
    ...     print("{0:10.1f} ".format(r[0]), end="")
    ...     # doctest: +NORMALIZE_WHITESPACE
    ...     for pn in r[1]:
    ...         print("{0:10.3f} ".format(pn), end="")
    ...         # doctest: +NORMALIZE_WHITESPACE
    ...     print("") # doctest: +NORMALIZE_WHITESPACE
    1.0      0.995      0.005      0.000      0.000      0.000
    2.0      0.956      0.044      0.001      0.000      0.000
    3.0      0.858      0.130      0.012      0.001      0.000
    4.0      0.695      0.252      0.047      0.005      0.001
    5.0      0.493      0.347      0.127      0.028      0.005
    6.0      0.295      0.362      0.219      0.091      0.026
    7.0      0.141      0.285      0.265      0.179      0.085
    8.0      0.056      0.159      0.228      0.229      0.161
    9.0      0.019      0.066      0.135      0.192      0.192
    10.0      0.003      0.019      0.054      0.106      0.150

    """

    try:
        from Corrfunc._countpairs import countspheres_vpf as vpf_extn
    except ImportError:
        msg = "Could not import the C extension for the Counts-in-Cells "\
              " (vpf)"
        raise ImportError(msg)

    import numpy as np
    from future.utils import bytes_to_native_str
    from Corrfunc.utils import translate_isa_string_to_enum
    from math import pi

    if numpN <= 0:
        msg = "Number of counts-in-cells wanted must be at least 1"
        raise ValueError(msg)

    if boxsize > 0.0:
        volume = boxsize * boxsize * boxsize
    else:
        volume = (max(X) - min(X)) * \
                 (max(Y) - min(Y)) * \
                 (max(Z) - min(Z))

    volume_sphere = 4. / 3. * pi * rmax * rmax * rmax
    if nspheres * volume_sphere > volume:
        msg = "There are not as many independent volumes in the "\
              "requested particle distribution. Num. spheres = {0} "\
              "rmax = {1} => effective volume = {2}.\nVolume of particles ="\
              "{3}. Reduce rmax or Nspheres"\
              .format(nspheres, rmax, nspheres * volume_sphere, volume)
        raise ValueError(msg)

    integer_isa = translate_isa_string_to_enum(isa)
    extn_results, api_time = vpf_extn(rmax, nbins,
                                      nspheres,
                                      numpN,
                                      seed,
                                      X, Y, Z,
                                      verbose=verbose,
                                      periodic=periodic,
                                      boxsize=boxsize,
                                      c_api_timer=c_api_timer,
                                      isa=integer_isa)

    if extn_results is None:
        msg = "RuntimeError occurred"
        raise RuntimeError(msg)

    results_dtype = np.dtype([(bytes_to_native_str(b'rmax'), np.float),
                              (bytes_to_native_str(b'pN'),
                               (np.float, numpN))])
    nbin = len(extn_results)
    results = np.zeros(nbin, dtype=results_dtype)

    for ii, r in enumerate(extn_results):
        results['rmax'][ii] = r[0]
        if numpN == 1:
            results['pN'] = r[1]
        else:
            for j in range(numpN):
                results['pN'][ii][j] = r[1 + j]

    if not c_api_timer:
        return results
    else:
        return results, api_time


if __name__ == '__main__':
    import doctest
    doctest.testmod()
