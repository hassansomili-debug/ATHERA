"""«لا أعرف» حالةً أولى | The unknown human decision (S5C).

الباحث الذي راجع حقلًا ولم يستطع الحكم عليه **لم يرفضه**. والرفض حكمٌ:
«هذا غير صحيح». و«لا أعرف» امتناعٌ عن الحكم. وخلطهما يفسد إشارتين معًا:
يجعل التردّد يبدو بطلانًا، ويجعل عدّ المرفوضات يضخّم ما لم يُرفض.

فالحالات أربع لا ثلاث:

  unverified  لم تُراجَع بعد
  approved    راجعها الباحث وأكّدها
  rejected    راجعها الباحث وحكم ببطلانها
  unknown     راجعها الباحث ولم يستطع الحكم

وقيمة خامسة تبقى ممنوعة: القيد يتّسع بقيمة معلومة لا ينفتح على نصّ حرّ.
"""
import sqlalchemy as sa
from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None

# الاسم الفعلي في القاعدة — فُحص لا خُمِّن.
#
# اتفاقية التسمية في `Base.metadata` تسبق كل قيد بـ`ck_%(table_name)s_`،
# وترحيل 0005 مرّر اسمًا يبدأ بـ`ck_` أصلًا، فتضاعفت البادئة. وكتابة الاسم
# صريحًا هنا تمنع `op.drop_constraint` من إعادة تطبيق الاتفاقية عليه فينتج
# اسمٌ ثالث لا وجود له.
CONSTRAINT = "ck_fact_candidates_ck_candidate_status"

OLD_VALUES = "'unverified','approved','rejected'"
NEW_VALUES = "'unverified','approved','rejected','unknown'"


def upgrade() -> None:
    op.execute(f"ALTER TABLE fact_candidates DROP CONSTRAINT {CONSTRAINT}")
    op.execute(
        f"ALTER TABLE fact_candidates ADD CONSTRAINT {CONSTRAINT} "
        f"CHECK (status IN ({NEW_VALUES}))"
    )

    # **ولا ترحيل بيانات.** لا صفّ إنتاجي يحمل `human_decision = unknown`:
    # مسار «لا أعرف» لم يُنشر بعد. وإعادة تصنيف صفوف قائمة بالتخمين تغيّر
    # قرارًا بشريًّا لم يقله صاحبه — وهو أسوأ من ترك الصفوف كما هي.
    #
    # ولو وُجدت صفوف تطويرية من S5C فمكانها بيئة التطوير، لا ترحيلٌ يمرّ
    # على الإنتاج ليصلحها.


def downgrade() -> None:
    """التنازل يرفض ولا يحوّل قرارًا (§4).

    `unknown → rejected` يقلب امتناعًا عن الحكم إلى حكمٍ بالبطلان، و
    `unknown → unverified` يمحو أن الباحث راجع الحقل أصلًا. كلاهما إتلافُ
    قرارٍ بشري لإرضاء تنازل — فيُرفض التنازل بدلًا منه.

    ومن أراده يحسم تلك الصفوف أولًا: اعتمادًا أو رفضًا صريحًا من الباحث.
    """
    remaining = op.get_bind().execute(
        sa.text("SELECT count(*) FROM fact_candidates WHERE status = 'unknown'")
    ).scalar_one()
    if remaining:
        raise RuntimeError(
            f"downgrade refused: {remaining} candidate(s) carry status='unknown'. "
            "Mapping them to 'rejected' or 'unverified' would destroy a human "
            "decision. Resolve them explicitly (approve or reject) first. | "
            f"التنازل مرفوض: {remaining} مرشّحًا بحالة «لا أعرف». تحويلها إلى "
            "«مرفوض» أو «غير مراجَع» إتلافٌ لقرار بشري — احسمها صراحةً أولًا."
        )

    op.execute(f"ALTER TABLE fact_candidates DROP CONSTRAINT {CONSTRAINT}")
    op.execute(
        f"ALTER TABLE fact_candidates ADD CONSTRAINT {CONSTRAINT} "
        f"CHECK (status IN ({OLD_VALUES}))"
    )
