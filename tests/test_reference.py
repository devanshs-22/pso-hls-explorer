"""Checks against the HarDMark reference tool (tutorial PDF, DCT-4pt, 1 adder + 2 multipliers).

Run:  .venv/bin/python -m unittest -v
"""
import unittest

from psodse.cost import Evaluator
from psodse.io import read_dfg, read_library
from psodse.pso import PSO, PSOConfig


class ReferenceTool(unittest.TestCase):
    def setUp(self):
        # the tutorial screenshot uses Ac = Lc = 0
        self.ev = Evaluator(read_dfg("inputs/DCT_4pt.txt"), read_library("inputs/DCT_4pt_lib.txt"),
                            area_constraint=0, latency_constraint=0)

    def test_schedule_matches_tutorial(self):
        p = self.ev.evaluate((1, 2))
        self.assertEqual(p.schedule.steps, [[1, 2], [3, 4, 5], [6], [7]])

    def test_area_latency_cost_match_tutorial(self):
        p = self.ev.evaluate((1, 2))
        self.assertEqual(p.regs.n_registers, 8)
        self.assertAlmostEqual(p.area, 176.1608, places=4)
        self.assertAlmostEqual(p.latency, 662.428, places=3)
        self.assertAlmostEqual(p.cost, 0.5633482281883153, places=12)

    def test_default_constraints_make_every_cost_negative(self):
        for bench, lib in [("DCT_4pt", "DCT_4pt_lib"), ("DCT_8pt", "DCT_8pt_lib"),
                           ("DWT_bechmark", "DWT_lib")]:
            ev = Evaluator(read_dfg(f"inputs/{bench}.txt"), read_library(f"inputs/{lib}.txt"))
            self.assertEqual((ev.ac, ev.lc), (ev.amax, ev.lmax))
            for pos in ev.all_positions():
                p = ev.evaluate(pos)
                self.assertLess(p.cost, 0, f"{bench} {pos}")
                # same ranking as Ac = Lc = 0: exactly 1 lower
                self.assertAlmostEqual(p.cost, p.area / ev.amax * ev.t1 + p.latency / ev.lmax * ev.t2 - 1, places=12)
        self.assertAlmostEqual(self.ev.evaluate((1, 2)).cost - 1,
                               Evaluator(read_dfg("inputs/DCT_4pt.txt"),
                                         read_library("inputs/DCT_4pt_lib.txt")).evaluate((1, 2)).cost, places=12)

    def test_register_sharing_has_no_conflicts(self):
        for pos in self.ev.all_positions():
            regs = self.ev.evaluate(pos).regs
            for row in regs.table:
                named = [v for v in row if v]
                self.assertEqual(len(named), len(set(named)))

    def test_pso_finds_exhaustive_optimum(self):
        for bench, lib in [("DCT_4pt", "DCT_4pt_lib"), ("DCT_8pt", "DCT_8pt_lib"),
                           ("DWT_bechmark", "DWT_lib")]:
            ev = Evaluator(read_dfg(f"inputs/{bench}.txt"), read_library(f"inputs/{lib}.txt"))
            best = min((ev.evaluate(p) for p in ev.all_positions()), key=lambda p: p.cost)
            for n in (3, 5, 7):
                for seed in range(5):
                    res = PSO(ev, PSOConfig(n_particles=n, seed=seed)).run()
                    self.assertAlmostEqual(res.best.cost, best.cost, places=12, msg=f"{bench} N={n}")
                    self.assertLessEqual(res.iterations_run, 50)


if __name__ == "__main__":
    unittest.main()


class PaperTable3(unittest.TestCase):
    """The five filters of Anshul & Sengupta (2023), written as DFGs in inputs/paper_filters/.
    At the configuration the paper reports, area and latency must equal its Table 3."""
    TABLE3 = {"BF": ((3, 1), 147.849, 927.399), "SF": ((4, 2), 243.79, 794.91),
              "LED": ((2, 2), 199.75, 728.671), "VE": ((1, 1), 99.09, 596.185),
              "HE": ((1, 1), 99.09, 596.185)}

    def test_area_and_latency_match_table3(self):
        for name, (pos, area, latency) in self.TABLE3.items():
            ev = Evaluator(read_dfg(f"inputs/paper_filters/{name}.txt"),
                           read_library(f"inputs/paper_filters/{name}_lib.txt"))
            p = ev.evaluate(pos)
            self.assertAlmostEqual(p.area, area, delta=0.005, msg=name)
            self.assertAlmostEqual(p.latency, latency, delta=0.005, msg=name)

    def test_sharpening_schedule_matches_fig3(self):
        ev = Evaluator(read_dfg("inputs/paper_filters/SF.txt"), read_library("inputs/paper_filters/SF_lib.txt"))
        p = ev.evaluate((4, 2))
        self.assertEqual(p.schedule.steps, [[1, 2, 3, 4, 5, 10], [6, 7, 8, 9], [11, 12, 16, 17],
                                            [13, 18], [14, 19], [15, 20]])
        self.assertEqual(p.regs.n_registers, 22)          # 22 rows in Table 1 of the paper
