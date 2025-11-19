"""
Deterministic quantizer for testing purposes.
Overrides random padding with deterministic padding.
"""
import sys
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'feature-encryption'))

from src.quantizer import FeatureQuantizer


class DeterministicQuantizer(FeatureQuantizer):
    """
    Test-only quantizer that uses deterministic padding instead of random padding.

    This allows register() and authenticate() to produce consistent results
    even when random padding is needed, enabling testing of 3.2 module logic
    without fixing the 3.1 random padding issue.
    """

    @staticmethod
    def _generate_secure_random_bits(n: int) -> List[int]:
        """
        Override to generate DETERMINISTIC bits for testing.

        Instead of random bits, return alternating pattern: [0, 1, 0, 1, ...]
        This ensures consistent results across register/authenticate calls.

        Args:
            n: Number of bits needed

        Returns:
            List[int]: Deterministic bit pattern
        """
        # Use alternating pattern for determinism
        return [i % 2 for i in range(n)]
