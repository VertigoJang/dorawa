package com.vertigojang.dorawa.data

import io.ktor.client.HttpClient
import io.ktor.client.call.body
import io.ktor.client.engine.okhttp.OkHttp
import io.ktor.client.plugins.contentnegotiation.ContentNegotiation
import io.ktor.client.request.get
import io.ktor.client.request.header
import io.ktor.client.request.post
import io.ktor.client.request.setBody
import io.ktor.http.ContentType
import io.ktor.http.contentType
import io.ktor.serialization.kotlinx.json.json
import kotlinx.serialization.json.Json

// 서버 통신. 노트북 앱의 api.py 와 같은 /api/app/* 엔드포인트를 호출.
class DorawaApi {
    var baseUrl: String = "https://dorawa.duckdns.org"
    var token: String = ""

    private val client = HttpClient(OkHttp) {
        install(ContentNegotiation) {
            json(Json { ignoreUnknownKeys = true })
        }
    }

    private fun url(path: String) = baseUrl.trimEnd('/') + path

    suspend fun login(username: String, password: String): LoginResponse {
        val r: LoginResponse = client.post(url("/api/app/login")) {
            contentType(ContentType.Application.Json)
            setBody(LoginRequest(username, password))
        }.body()
        if (r.token.isNotEmpty()) token = r.token
        return r
    }

    suspend fun register(username: String, email: String, password: String): OkResponse =
        client.post(url("/api/app/register")) {
            contentType(ContentType.Application.Json)
            setBody(RegisterRequest(username, email, password))
        }.body()

    suspend fun verify(username: String, code: String): LoginResponse {
        val r: LoginResponse = client.post(url("/api/app/verify")) {
            contentType(ContentType.Application.Json)
            setBody(VerifyRequest(username, code))
        }.body()
        if (r.token.isNotEmpty()) token = r.token
        return r
    }

    suspend fun forgot(email: String): OkResponse =
        client.post(url("/api/app/forgot")) {
            contentType(ContentType.Application.Json)
            setBody(ForgotRequest(email))
        }.body()

    suspend fun reset(email: String, code: String, password: String): OkResponse =
        client.post(url("/api/app/reset")) {
            contentType(ContentType.Application.Json)
            setBody(ResetRequest(email, code, password))
        }.body()

    suspend fun devices(): List<Device> =
        client.get(url("/api/app/devices")) {
            header("Authorization", "Bearer $token")
        }.body<DevicesResponse>().devices

    suspend fun reports(deviceId: Int): List<Report> =
        client.get(url("/api/app/device/$deviceId/reports")) {
            header("Authorization", "Bearer $token")
        }.body<ReportsResponse>().reports

    suspend fun setLost(deviceId: Int, lost: Boolean): OkResponse =
        client.post(url("/api/app/device/$deviceId/lost")) {
            header("Authorization", "Bearer $token")
            contentType(ContentType.Application.Json)
            setBody(LostRequest(lost))
        }.body()

    suspend fun capture(deviceId: Int, cmd: String): OkResponse =
        client.post(url("/api/app/device/$deviceId/capture")) {
            header("Authorization", "Bearer $token")
            contentType(ContentType.Application.Json)
            setBody(CaptureRequest(cmd))
        }.body()

    // 토큰을 붙인 이미지 URL (서버가 상대경로 + token 쿼리로 내려줌)
    fun mediaUrl(path: String?): String? =
        if (path.isNullOrEmpty()) null else baseUrl.trimEnd('/') + path
}
