def calculate_structure_metrics(results_by_tf, bias):
    """
    Converts ICT structures into numeric quality metrics.
    """

    liquidity_strength = 0
    fvg_quality = 0
    htf_alignment = 0

    aligned_tfs = 0
    total_tfs = 0

    for tf, result in results_by_tf.items():

        if not result:
            continue

        total_tfs += 1

        ob = result.get("ob")
        liq = result.get("liquidity")
        fvg = result.get("fvg")

        if ob and ob.get("type") == bias:
            aligned_tfs += 1

        if liq and liq.get("has_liquidity"):

            liquidity_strength += 1

            if liq.get("swept"):
                liquidity_strength += 2

        if fvg and bias in fvg.get("type", ""):
            fvg_quality += 1

    if total_tfs:
        htf_alignment = aligned_tfs / total_tfs

    return {
        "liquidity_strength": liquidity_strength,
        "fvg_quality": round(fvg_quality, 2),
        "htf_alignment": round(htf_alignment, 3)
    }