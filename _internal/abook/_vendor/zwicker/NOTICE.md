# MoSQITo 1.2.1 stationary subset

Upstream: https://github.com/Eomys/MoSQITo/tree/v1.2.1
Copyright MoSQITo Developers. Apache-2.0; see LICENSE.

Copied from the supplied dev install. Only package imports changed to relative imports; numerical algorithms unchanged. No pyuff, plots, time-varying meter, or other metrics included. Uses existing numpy and scipy.

[
  {
    "source": "sq_metrics/loudness/loudness_zwst/loudness_zwst.py",
    "source_sha256": "d2559cef63c10242827fca29f5b5fb366d34593953c91588f2bc48d1ed3eec31",
    "bytes": 3878
  },
  {
    "source": "sq_metrics/loudness/loudness_zwst/_main_loudness.py",
    "source_sha256": "6cc3ba726a89911eac14f5f1d714a09615475b8c47ae2dc672bfa1b4aa08ec21",
    "bytes": 7446
  },
  {
    "source": "sq_metrics/loudness/loudness_zwst/_calc_slopes.py",
    "source_sha256": "35f3af5f8ad285be2d5c1778be2c3ba38caff425c086a00ac06300a3f22f33f3",
    "bytes": 14217
  },
  {
    "source": "sq_metrics/loudness/loudness_zwst/_get_rns_index.py",
    "source_sha256": "224cc41204a1e47d772f9fff10d7365c368078d4a4778bd7a09429d45000b176",
    "bytes": 1230
  },
  {
    "source": "sound_level_meter/noct_spectrum/noct_spectrum.py",
    "source_sha256": "074d61c814bf3c17736efdb425330eba5c5e2c26c7ffbe69d8e3e233149e43df",
    "bytes": 2901
  },
  {
    "source": "sound_level_meter/noct_spectrum/_filter_bandwidth.py",
    "source_sha256": "16ec546b61e77218296dace720baac1eaeb7bdd70c8dc2bca22e1bb22f32d075",
    "bytes": 2087
  },
  {
    "source": "sound_level_meter/noct_spectrum/_n_oct_time_filter.py",
    "source_sha256": "1897b8a047e1cf0552322ca454228878f327bb487fad7c6a44728e0b079eb0be",
    "bytes": 1957
  },
  {
    "source": "sound_level_meter/noct_spectrum/_center_freq.py",
    "source_sha256": "58ef4ab46f0662e4e297828914185bd67c0a9a884b00f248dc795317290d6738",
    "bytes": 2214
  },
  {
    "source": "sound_level_meter/noct_spectrum/_nominal_frequency.py",
    "source_sha256": "9c31133888276b86fa62676a210a161d1be8494fb36ee55c4e7b3a9685c70a2d",
    "bytes": 762
  },
  {
    "source": "utils/conversion/amp2db.py",
    "source_sha256": "0c8ee1adeb15c0a945dcaade3c0009e464daa5cb3d92125a2a62b5213e279e93",
    "bytes": 644
  }
]
