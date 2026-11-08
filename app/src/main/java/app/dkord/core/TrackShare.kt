package app.dkord.core

/** Plain text only: no Android dependency, account data, or session URLs. */
fun trackShareText(track: Track): String =
    if (isLocalAudioId(track.id)) "${track.title} - ${track.artist}"
    else "${track.title} - ${track.artist}\nhttps://music.youtube.com/watch?v=${track.id}"
