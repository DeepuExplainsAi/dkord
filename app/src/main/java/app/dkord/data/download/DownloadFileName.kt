package app.dkord.data.download

private val RESERVED_FILE_NAMES = setOf("CON", "PRN", "AUX", "NUL") +
    (1..9).flatMap { listOf("COM$it", "LPT$it") }

/** New leaf names only: keep metadata/old URIs unchanged, and leave room for collision suffixes. */
internal fun downloadFileName(artist: String, title: String, ext: String): String {
    require(ext.matches(Regex("[A-Za-z0-9]{1,8}"))) { "Invalid audio extension" }
    var clean = "$artist - $title".replace(Regex("[\\\\/:*?\"<>|\\p{Cntrl}]"), "")
        .replace(Regex("\\s+"), " ").trim('.', ' ', '-')
    if (clean.substringBefore('.').uppercase() in RESERVED_FILE_NAMES) clean = "Dkord $clean"
    val base = buildString {
        var bytes = 0
        for (point in clean.codePoints().toArray()) {
            val text = String(Character.toChars(point))
            val size = text.toByteArray(Charsets.UTF_8).size
            if (length + text.length > 120 || bytes + size > 220) break
            append(text); bytes += size
        }
    }.trim('.', ' ', '-').ifBlank { "track" }
    return "$base.$ext"
}
