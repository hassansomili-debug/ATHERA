"""AT-S8-07…11 — المخرجات والتفسير وبيئة التنفيذ والأدوات (§18، §31.6، §39)."""
import pytest

from athera_api.services.analysis import exports, interpretation, reproducibility, vocab


def test_an_output_cannot_exist_without_a_run():
    """AT-S8-07 — §39: «النتائج غير المرتبطة بتحليل: صفر»."""
    output = reproducibility.AnalysisOutput(
        output_id="o1", run_id="run-3", output_kind="table",
        label_ar="جدول الارتباطات", payload={"r": 0.42},
    )
    assert output.run_id == "run-3"

    with pytest.raises(reproducibility.ReproducibilityError):
        reproducibility.AnalysisOutput(output_id="o2", run_id="   ", output_kind="table",
                                       label_ar="جدول", payload={})


def test_sandbox_forbids_outbound_network_and_zero_quotas():
    """AT-S8-11 — §31.6."""
    assert reproducibility.SandboxSpec().network_egress is False
    with pytest.raises(reproducibility.ReproducibilityError):
        reproducibility.SandboxSpec(network_egress=True)
    with pytest.raises(reproducibility.ReproducibilityError):
        reproducibility.SandboxSpec(max_memory_mb=0)


# ── AT-S8-08/09: طبقات التفسير (§18.3) ──

def test_the_four_layers_stay_separate():
    assert len(vocab.INTERPRETATION_LAYERS) == 4
    record = interpretation.Interpretation(
        output_id="o1", result_ar="معامل الارتباط 0.42",
        statistical_ar="ارتباط موجب متوسط ودال",
        theoretical_ar="يتسق مع نظرية السلوك المخطط",
        managerial_ar="يمكن للمعلن التركيز على بناء الثقة",
    )
    assert record.layers_present == ["result", "statistical", "theoretical", "managerial"]
    assert len(interpretation.layers(record)) == 4


def test_an_interpretation_needs_an_actual_output():
    """AT-S8-09 — §18.3: «يفسر النتائج الفعلية فقط»."""
    with pytest.raises(interpretation.InterpretationError):
        interpretation.Interpretation(output_id="", result_ar="نتيجة")
    with pytest.raises(interpretation.InterpretationError):
        interpretation.Interpretation(output_id="o1", result_ar="   ")


def test_each_layer_requires_the_one_beneath_it():
    with pytest.raises(interpretation.InterpretationError):
        interpretation.Interpretation(output_id="o1", result_ar="ن",
                                      theoretical_ar="نظري بلا إحصائي")
    with pytest.raises(interpretation.InterpretationError):
        interpretation.Interpretation(output_id="o1", result_ar="ن", statistical_ar="إحصائي",
                                      managerial_ar="إداري بلا نظري")


def test_merging_the_layers_is_explicitly_refused():
    with pytest.raises(interpretation.InterpretationError):
        interpretation.merged_text_is_refused("نص مدموج")


# ── AT-S8-10: الأدوات وحدودها المعلنة (§18.2، §47.9) ──

def test_every_tool_declares_what_it_does_not_support():
    """ادعاء توافق كامل مع صيغة مغلقة أسوأ من الاعتراف بالحد."""
    capabilities = exports.all_capabilities()
    assert len(capabilities) == 5
    for capability in capabilities:
        assert capability.not_supported_ar.strip() and capability.not_supported_en.strip()
        assert any("؀" <= ch <= "ۿ" for ch in capability.not_supported_ar)


@pytest.mark.parametrize("tool", ["smartpls", "nvivo"])
def test_binary_formats_are_declared_unsupported(tool):
    assert "الثنائية" in exports.capability(tool).not_supported_ar


def test_unknown_tool_is_refused():
    with pytest.raises(exports.ExportError):
        exports.capability("stata")


def test_smartpls_checklists_name_what_is_missing():
    measurement = exports.smartpls_checklist("measurement",
                                             {"construct_type", "indicator_loadings"})
    assert len(measurement.items) == 6
    assert "convergent_validity" in measurement.missing
    assert not measurement.is_complete

    complete = exports.smartpls_checklist(
        "measurement", {key for key, _, _ in exports.MEASUREMENT_MODEL_CHECKS}
    )
    assert complete.is_complete

    assert len(exports.smartpls_checklist("structural", set()).items) == 5
    with pytest.raises(exports.ExportError):
        exports.smartpls_checklist("magic", set())


def test_spss_syntax_is_generated_for_review_not_execution():
    """§18.1 — التحليل يقع في بيئة حسابية، لا داخل نص توليدي."""
    syntax = exports.spss_syntax("regression", ["y", "x1", "x2"],
                                 dataset_label="بيانات الاستبانة")
    assert "REGRESSION" in syntax and "/DEPENDENT y" in syntax
    assert "Review before running" in syntax

    with pytest.raises(exports.ExportError):
        exports.spss_syntax("sem", ["y"], dataset_label="x")
    with pytest.raises(exports.ExportError):
        exports.spss_syntax("descriptive", [], dataset_label="x")


def test_nvivo_codebook_uses_an_open_format():
    book = exports.nvivo_codebook([("C1", "الثقة في الإعلان", "المبحوث ذكر أنه يثق")])
    assert book[0]["code"] == "C1" and book[0]["definition_ar"]
    with pytest.raises(exports.ExportError):
        exports.nvivo_codebook([])
