package app.dkord.core

/** Not a provider video id. Never send generated audio identities/metadata to remote services. */
const val LOCAL_STUDIO_PREFIX = "local-studio-"
fun isLocalAudioId(id: String): Boolean = id.startsWith(LOCAL_STUDIO_PREFIX)
