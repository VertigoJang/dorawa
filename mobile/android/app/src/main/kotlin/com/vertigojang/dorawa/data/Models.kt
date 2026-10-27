package com.vertigojang.dorawa.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class LoginResponse(
    val token: String = "",
    val username: String = "",
    val error: String = "",
)

@Serializable
data class Device(
    val id: Int,
    val name: String? = null,
    val lost: Boolean = false,
    @SerialName("camera_mode") val cameraMode: String = "remote",
    @SerialName("auto_interval") val autoInterval: Int = 5,
    @SerialName("pending_cmd") val pendingCmd: String = "",
)

@Serializable
data class DevicesResponse(val devices: List<Device> = emptyList())

@Serializable
data class Report(
    val ts: Double = 0.0,
    @SerialName("public_ip") val publicIp: String? = null,
    @SerialName("ip_desc") val ipDesc: String? = null,
    @SerialName("wifi_ssid") val wifiSsid: String? = null,
    val lat: Double? = null,
    val lng: Double? = null,
    val accuracy: Double? = null,
    @SerialName("photo_url") val photoUrl: String? = null,
    @SerialName("video_url") val videoUrl: String? = null,
    val raw: String? = null,
)

@Serializable
data class ReportsResponse(val reports: List<Report> = emptyList())

@Serializable
data class OkResponse(val ok: Boolean = false, val error: String = "")

// --- 요청 본문 ---
@Serializable
data class LoginRequest(val username: String, val password: String)

@Serializable
data class LostRequest(val lost: Boolean)

@Serializable
data class CaptureRequest(val cmd: String)

@Serializable
data class RegisterRequest(val username: String, val email: String, val password: String)

@Serializable
data class VerifyRequest(val username: String, val code: String)

@Serializable
data class ForgotRequest(val email: String)

@Serializable
data class ResetRequest(val email: String, val code: String, val password: String)
