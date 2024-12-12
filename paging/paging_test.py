from paging import Processor
import pytest

def pml4_testcases() -> tuple[tuple[int, int]]:
    return (
        ( 0b1111_1111_1111_1010_1010_1000_0000_0000, 0b1_0101_0101),
    )

# @pytest.mark.parametrize("pml4e, avaiting", pml4_testcases())
# def test_processor_PML4(pml4e: int, avaiting: int) -> None:
#     assert Processor.pml4(pml4e) == avaiting
