#!/usr/bin/env python3
# coding=utf-8
import sys
from time import sleep
import logging as log


class Processor:
    def __init__(self, CR3: int):
        log.debug(f"Initializing Processor with CR3: 0x{CR3:08X}")
        self._CR3: int = CR3
        self._phymem: dict[int, int] = {}

    @property
    def CR3(self) -> int:
        return self._CR3

    @CR3.setter
    def CR3(self, value: int) -> None:
        log.debug(f"Setting CR3 to: 0x{value:08X}")
        self._CR3 = value


    def read_mem(self, phyaddr: int) -> int:
        qword: int | None = self._phymem.get(phyaddr)
        return qword if qword else 0


    def write_mem(self, phyaddr: int, value: int) -> None:
        log.debug(f"phymem[0x{phyaddr:08X}] = 0x{value:08X}")
        self._phymem[phyaddr] = value


    @staticmethod
    def extract_bits(value: int, left: int, right: int) -> int:
        """
        Extract bits from a value.
        """
        # log.debug(f"Extract bits from {value:064b} with left={left} and right={right}")
        LEFT_MASK: int = (-1) << (left - right + 1)
        bits = (value >> right) & (~LEFT_MASK)
        # log.debug(f"Extracted bits: {bits:064b}")
        return bits


    @staticmethod
    def set_bits(bits: int, target: int, left: int, right: int) -> int:
        """
        Set bits in a value.
        """
        # log.debug(f"Setting {bits:064b} in {target:064b} with left={left} and right={right}")
        LEFT_MASK: int = (-1) << left
        RIGHT_MASK: int = ~( ((-1) >> right) << right )
        MASK = LEFT_MASK | RIGHT_MASK
        cleared_bits: int = bits & MASK
        cleared_value: int = (target << right) & ~MASK
        result = cleared_value | cleared_bits
        # log.debug(f"result: {result:064b}")
        return result

    
    def _translate_entry(self, tbl_entry: int) -> int | None:
        """
        Translate a table entry into a physical address.

        A table entry is translated into a physical address if the "persist" bit
        is set in the flags. If the persist bit is not set, None is returned.
        """
        flags: int = Processor.extract_bits(tbl_entry, 11, 0)
        persist = flags & 1 == 1
        if not persist:
            log.debug("translate_entry 0x{tbl_entry:08X} fail:"\
                      "persit flag ing {flags:04X} is 0")
            return None
        return Processor.extract_bits(tbl_entry, 51, 12) << 12

    
    def _PML4(self, laddr: int) -> int | None:
        """Retrieve the PML4 entry for the directory table from a logical address.

        This method extracts the PML4E (Page Map Level 4 Entry) from the given
        logical address by calculating the appropriate offset. It performs
        validation on the highest bits to ensure correct sign extension and
        returns the corresponding value from physical memory if validation succeeds.
        """
        # Extract the PML4E offset from the logical address
        pml4e_offset: int = Processor.extract_bits(laddr, 47, 39)

        # Read and return the PML4 entry from physical memory
        return self.read_mem(self.CR3 + pml4e_offset * 8)

    def _PDPT(self, laddr: int, pml4e: int | None) -> int | None:
        """Return the Page Directory Pointer Table Entry (PDPTE) from a logical address and PML4 entry.

        This method calculates the offset for the PDPTE within the Page Directory 
        Pointer Table using the provided logical address and PML4 entry, then reads 
        the PDPTE from physical memory.
        """
        if not pml4e: return None

        # Translate the PML4 entry to get the directory pointer address
        dir_ptr: int | None = self._translate_entry(pml4e)
        if not dir_ptr:
            log.debug(f"Fail to translate PML4E 0x{pml4e:08X}")
            return None

        # Extract the directory pointer offset from the logical address
        dp_offset: int = Processor.extract_bits(laddr, 38, 30)

        # Read and return the PDPTE from physical memory
        return self.read_mem(dir_ptr + dp_offset * 8)

    def _PD(self, ladd: int, pdpte: int | None) -> int | None:
        """Return page directory entry (PDE).

        The page directory entry is read from the page directory table.
        The page directory table is identified by the page directory pointer
        extracted from the page map level 4 entry.
        """
        if not pdpte: return None
        
        pd_offset: int = Processor.extract_bits(ladd, 29, 21)
        # The page directory pointer is extracted from the page map level 4 entry
        dir_entry: int | None = self._translate_entry(pdpte)
        if not dir_entry: 
            log.debug(f"Fail to translate PDPTE 0x{pdpte:08X}")
            return None

        # The page directory entry is read from the page directory table
        return self.read_mem(dir_entry + pd_offset * 8)


    def _PT(self, laddr: int, pde: int | None) -> int | None:
        """
        Return the page table entry (PTE) from a logical address and page directory entry.

        The page table entry is read from the page table identified by the page directory entry.
        The page directory entry is used to translate the logical address to a physical address.
        If the translation fails, None is returned.
        """
        if not pde: return None

        # Extract the table offset from the logical address
        table_offset: int = Processor.extract_bits(laddr, 20, 12)

        # Translate the page directory entry to get the page table entry
        table_entry: int | None = self._translate_entry(pde)
        if not table_entry: 
            log.debug(f"Fail to translate PDE 0x{pde:08X}")
            return None

        # Read and return the page table entry from physical memory
        return self.read_mem(table_entry + table_offset * 8)


    def _phyaddr(self, laddr: int, pte: None | int) -> int | None:
        """
        Return the physical address from a logical address and page table entry.

        The physical address is the page table entry with the offset from the logical address.
        The page table entry is translated to a physical address using the translate_entry method.
        If the translation fails, None is returned.
        """
        if not pte: return None

        # Translate the page table entry to get the page frame number
        page: int | None = self._translate_entry(pte)
        if not page:
            log.debug(f"Fail to translate PTE 0x{pte:08X}")
            return None

        # Extract the page offset from the logical address
        offset: int = Processor.extract_bits(laddr, 11, 0)

        # Combine the page frame number with the offset to get the physical address
        return page | offset


    def translate(self, laddr: int) -> int | None:
        """
        Translate a logical address to a physical address.

        The translation is done by reading the page table entries from the page
        tables and combining them with the offset from the logical address.

        If any of the page table entries are invalid or if the translation fails,
        None is returned.
        """
        log.debug(f"Process laddr {laddr:<16} 0x{laddr:08X}")

        # Read the page map level 4 entry (PML4E) from the page map level 4 table
        pml4e: int | None = self._PML4(laddr)
        # Read the page directory pointer table entry (PDPTE) from the page directory pointer table
        pdpte: int | None = self._PDPT(laddr, pml4e)
        # Read the page directory entry (PDE) from the page directory table
        pde: int | None = self._PD(laddr, pdpte)
        # Read the page table entry (PTE) from the page table
        pte: int | None = self._PT(laddr, pde)
        # Translate the page table entry to a physical address
        phyaddr: int | None = self._phyaddr(laddr, pte)

        if phyaddr:
            log.debug(f"    pml4e= {pml4e:<10} 0x{pml4e:08X} 0b{pml4e:064b}")
            log.debug(f"    pdpte= {pdpte:<10} 0x{pdpte:08X} 0b{pdpte:064b}")
            log.debug(f"    pde= {pde:<12} 0x{pde:08X} 0b{pde:064b}")
            log.debug(f"    pte= {pte:<13d} 0x{pte:08X} 0b{pte:064b}")
            log.debug(f"    phyadd= {phyaddr:<9d} 0x{phyaddr:08X} 0b{phyaddr:064b}")
        else:
            log.debug(f"    Fail, pml4e={pml4e}, pdpte={pdpte}, pde={pde}, pte={pte}, phyaddr={phyaddr}")

        return phyaddr



def main() -> None:
    """Read m physical addresses and their values from stdin. Read q logical addresses from stdin and
    translate them to physical addresses. If translation fails, print "fault".
    """
    reader = (tuple(map(int, ln.split())) for ln in sys.stdin)
    m: int
    q: int
    r: int
    m, q, r = next(reader)
    proc = Processor(r)

    addresses: tuple[tuple[int, ...], ...] = tuple(next(reader) for _ in range(m))
    for k, v in addresses:
        proc.write_mem(k, v)

    logic_addresses: list[int] = [int(next(reader)[0]) for _ in range(q)]

    for laddr in logic_addresses:
        phyaddr: int | None = proc.translate(laddr)
        print(f"{phyaddr}") if phyaddr else print("fault")


if __name__ == "__main__":
    lvl = log.DEBUG
    # lvl = log.CRITICAL
    log.basicConfig(level=lvl,
                        format='%(asctime)s %(levelname)s: %(message)s')
    main()
    log.shutdown()