from code_analyzer.complexity import analyze_source
from code_analyzer.models import ComplexityBand


def test_simple_file_low_complexity():
    code = "public class A { public int one(){ return 1; } }"
    m = analyze_source("A.java", code)
    assert m.function_count == 1
    assert m.band == ComplexityBand.LOW


def test_branchy_method_raises_complexity():
    code = """
    public class B {
      public int classify(int x) {
        if (x > 10) { return 1; }
        else if (x > 5) { return 2; }
        else if (x > 0) { return 3; }
        for (int i = 0; i < x; i++) { if (i % 2 == 0) { x++; } }
        return x > 0 ? x : -x;
      }
    }
    """
    m = analyze_source("B.java", code)
    assert m.max_cyclomatic_complexity >= 5
    assert m.most_complex_function is not None
    assert m.band in (ComplexityBand.MODERATE, ComplexityBand.HIGH, ComplexityBand.VERY_HIGH)


def test_unparseable_content_is_safe():
    m = analyze_source("weird.xyz", "::: not real code :::")
    assert m.nloc >= 0  # never raises
