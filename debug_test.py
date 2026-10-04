import sys
import os
sys.path.insert(0, os.path.abspath("."))
from tests.test_analyzer_blend import TestAnalyzerBlend
import unittest

class DebugRunner:
    def run(self):
        t = TestAnalyzerBlend("test_heuristic_agrees_with_ml_blended_probability")
        try:
            t.setUpClass()
            t.test_heuristic_agrees_with_ml_blended_probability()
        except AssertionError as e:
            print("AssertionError:", e)
        finally:
            t.tearDownClass()

if __name__ == "__main__":
    DebugRunner().run()
