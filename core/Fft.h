// Fft.h: a small in-place radix-2 FFT (copied from my-lil-vj-link), so analysis needs no extra dependency. No Rack dependency.
// Author: Ari Klopfer / A_Development. MIT
#pragma once
#include <cmath>
#include <complex>
#include <utility>
#include <vector>

namespace recycler
{
// Forward transform of a power-of-two sized buffer, in place.
inline void fft (std::vector<std::complex<double>>& a)
{
    const size_t n = a.size();
    for (size_t i = 1, j = 0; i < n; ++i)   // bit-reversal permutation
    {
        size_t bit = n >> 1;
        for (; j & bit; bit >>= 1) j ^= bit;
        j ^= bit;
        if (i < j) std::swap (a[i], a[j]);
    }
    for (size_t len = 2; len <= n; len <<= 1)
    {
        const double ang = -2.0 * 3.14159265358979323846 / (double) len;
        const double sr = std::cos (ang), si = std::sin (ang);
        for (size_t i = 0; i < n; i += len)
        {
            double wr = 1.0, wi = 0.0;
            for (size_t k = 0; k < len / 2; ++k)
            {
                // complex multiplies written out: std::complex's operator* calls __muldc3 (NaN/Inf rescue) per butterfly
                const std::complex<double> x = a[i + k + len / 2];
                const std::complex<double> u = a[i + k], v (x.real() * wr - x.imag() * wi, x.real() * wi + x.imag() * wr);
                a[i + k] = u + v;
                a[i + k + len / 2] = u - v;
                const double t = wr * sr - wi * si;
                wi = wr * si + wi * sr;
                wr = t;
            }
        }
    }
}
} // namespace recycler
