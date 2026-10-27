package com.vertigojang.dorawa

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.lifecycle.lifecycleScope
import com.vertigojang.dorawa.data.Device
import com.vertigojang.dorawa.data.DorawaApi
import com.vertigojang.dorawa.data.Report
import com.vertigojang.dorawa.ui.theme.DorawaTheme
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class MainActivity : ComponentActivity() {
    private val api = DorawaApi()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            DorawaTheme {
                Surface(Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
                    AppRoot(api)
                }
            }
        }
    }
}

private sealed class Screen {
    data object Login : Screen()
    data object Register : Screen()
    data class Verify(val username: String) : Screen()
    data object Forgot : Screen()
    data class Reset(val email: String) : Screen()
    data object DeviceList : Screen()
    data class DeviceDetail(val device: Device) : Screen()
}

@Composable
fun AppRoot(api: DorawaApi) {
    var screen by remember { mutableStateOf<Screen>(Screen.Login) }
    when (val s = screen) {
        is Screen.Login -> LoginScreen(api,
            onSuccess = { screen = Screen.DeviceList },
            onRegister = { screen = Screen.Register },
            onForgot = { screen = Screen.Forgot })
        is Screen.Register -> RegisterScreen(api,
            onNeedVerify = { screen = Screen.Verify(it) },
            onBack = { screen = Screen.Login })
        is Screen.Verify -> VerifyScreen(api, s.username,
            onSuccess = { screen = Screen.DeviceList },
            onBack = { screen = Screen.Login })
        is Screen.Forgot -> ForgotScreen(api,
            onSent = { screen = Screen.Reset(it) },
            onBack = { screen = Screen.Login })
        is Screen.Reset -> ResetScreen(api, s.email,
            onDone = { screen = Screen.Login },
            onBack = { screen = Screen.Login })
        is Screen.DeviceList -> DeviceListScreen(api,
            onOpen = { screen = Screen.DeviceDetail(it) },
            onLogout = { screen = Screen.Login })
        is Screen.DeviceDetail -> DeviceDetailScreen(api, s.device,
            onBack = { screen = Screen.DeviceList })
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun LoginScreen(api: DorawaApi, onSuccess: () -> Unit,
                onRegister: () -> Unit, onForgot: () -> Unit) {
    val scope = rememberCoroutineScope()
    var server by remember { mutableStateOf("https://dorawa.duckdns.org") }
    var user by remember { mutableStateOf("") }
    var pw by remember { mutableStateOf("") }
    var msg by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }

    Column(
        Modifier.fillMaxSize().padding(24.dp).verticalScroll(rememberScrollState()),
        verticalArrangement = Arrangement.Center,
    ) {
        Text("Dorawa", style = MaterialTheme.typography.headlineLarge)
        Spacer(Modifier.height(24.dp))
        OutlinedTextField(server, { server = it }, label = { Text("서버 주소") },
            singleLine = true, modifier = Modifier.fillMaxWidth())
        Spacer(Modifier.height(8.dp))
        OutlinedTextField(user, { user = it }, label = { Text("아이디") },
            singleLine = true, modifier = Modifier.fillMaxWidth())
        Spacer(Modifier.height(8.dp))
        OutlinedTextField(pw, { pw = it }, label = { Text("비밀번호") },
            singleLine = true, visualTransformation = PasswordVisualTransformation(),
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
            modifier = Modifier.fillMaxWidth())
        Spacer(Modifier.height(16.dp))
        Button(
            onClick = {
                msg = ""; busy = true
                api.baseUrl = server.trim()
                scope.launch {
                    try {
                        val r = api.login(user.trim(), pw)
                        if (r.token.isNotEmpty()) onSuccess()
                        else msg = r.error.ifEmpty { "로그인 실패" }
                    } catch (e: Exception) {
                        msg = "연결 실패: ${e.message}"
                    } finally { busy = false }
                }
            },
            enabled = !busy, modifier = Modifier.fillMaxWidth()
        ) { Text(if (busy) "로그인 중..." else "로그인") }
        if (msg.isNotEmpty()) {
            Spacer(Modifier.height(12.dp))
            Text(msg, color = MaterialTheme.colorScheme.error)
        }
        Spacer(Modifier.height(16.dp))
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            TextButton(onClick = onRegister) { Text("회원가입") }
            TextButton(onClick = onForgot) { Text("비밀번호 찾기") }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun RegisterScreen(api: DorawaApi, onNeedVerify: (String) -> Unit, onBack: () -> Unit) {
    val scope = rememberCoroutineScope()
    var user by remember { mutableStateOf("") }
    var email by remember { mutableStateOf("") }
    var pw by remember { mutableStateOf("") }
    var msg by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    Column(Modifier.fillMaxSize().padding(24.dp).verticalScroll(rememberScrollState()),
        verticalArrangement = Arrangement.Center) {
        Text("회원가입", style = MaterialTheme.typography.headlineMedium)
        Spacer(Modifier.height(16.dp))
        OutlinedTextField(user, { user = it }, label = { Text("아이디") }, singleLine = true, modifier = Modifier.fillMaxWidth())
        Spacer(Modifier.height(8.dp))
        OutlinedTextField(email, { email = it }, label = { Text("이메일 (인증 코드를 받습니다)") }, singleLine = true, modifier = Modifier.fillMaxWidth())
        Spacer(Modifier.height(8.dp))
        OutlinedTextField(pw, { pw = it }, label = { Text("비밀번호") }, singleLine = true,
            visualTransformation = PasswordVisualTransformation(), modifier = Modifier.fillMaxWidth())
        Spacer(Modifier.height(16.dp))
        Button(onClick = {
            msg = ""; busy = true
            scope.launch {
                try {
                    val r = api.register(user.trim(), email.trim(), pw)
                    if (r.ok) onNeedVerify(user.trim()) else msg = r.error.ifEmpty { "가입 실패" }
                } catch (e: Exception) { msg = "오류: ${e.message}" } finally { busy = false }
            }
        }, enabled = !busy, modifier = Modifier.fillMaxWidth()) { Text(if (busy) "처리 중..." else "가입하고 인증 코드 받기") }
        if (msg.isNotEmpty()) { Spacer(Modifier.height(12.dp)); Text(msg, color = MaterialTheme.colorScheme.error) }
        Spacer(Modifier.height(8.dp)); TextButton(onClick = onBack) { Text("← 로그인으로") }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun VerifyScreen(api: DorawaApi, username: String, onSuccess: () -> Unit, onBack: () -> Unit) {
    val scope = rememberCoroutineScope()
    var code by remember { mutableStateOf("") }
    var msg by remember { mutableStateOf("") }
    Column(Modifier.fillMaxSize().padding(24.dp).verticalScroll(rememberScrollState()),
        verticalArrangement = Arrangement.Center) {
        Text("이메일 인증", style = MaterialTheme.typography.headlineMedium)
        Spacer(Modifier.height(8.dp))
        Text("이메일로 받은 6자리 코드를 입력하세요.", style = MaterialTheme.typography.bodyMedium)
        Spacer(Modifier.height(16.dp))
        OutlinedTextField(code, { code = it }, label = { Text("6자리 코드") }, singleLine = true,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number), modifier = Modifier.fillMaxWidth())
        Spacer(Modifier.height(16.dp))
        Button(onClick = {
            msg = ""
            scope.launch {
                try {
                    val r = api.verify(username, code.trim())
                    if (r.token.isNotEmpty()) onSuccess() else msg = r.error.ifEmpty { "인증 실패" }
                } catch (e: Exception) { msg = "오류: ${e.message}" }
            }
        }, modifier = Modifier.fillMaxWidth()) { Text("인증하기") }
        if (msg.isNotEmpty()) { Spacer(Modifier.height(12.dp)); Text(msg, color = MaterialTheme.colorScheme.error) }
        Spacer(Modifier.height(8.dp)); TextButton(onClick = onBack) { Text("← 로그인으로") }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ForgotScreen(api: DorawaApi, onSent: (String) -> Unit, onBack: () -> Unit) {
    val scope = rememberCoroutineScope()
    var email by remember { mutableStateOf("") }
    var msg by remember { mutableStateOf("") }
    Column(Modifier.fillMaxSize().padding(24.dp).verticalScroll(rememberScrollState()),
        verticalArrangement = Arrangement.Center) {
        Text("비밀번호 찾기", style = MaterialTheme.typography.headlineMedium)
        Spacer(Modifier.height(8.dp))
        Text("가입한 이메일로 재설정 코드를 보냅니다.", style = MaterialTheme.typography.bodyMedium)
        Spacer(Modifier.height(16.dp))
        OutlinedTextField(email, { email = it }, label = { Text("가입한 이메일") }, singleLine = true, modifier = Modifier.fillMaxWidth())
        Spacer(Modifier.height(16.dp))
        Button(onClick = {
            msg = ""
            scope.launch {
                try { api.forgot(email.trim()); onSent(email.trim()) }
                catch (e: Exception) { msg = "오류: ${e.message}" }
            }
        }, modifier = Modifier.fillMaxWidth()) { Text("재설정 코드 받기") }
        if (msg.isNotEmpty()) { Spacer(Modifier.height(12.dp)); Text(msg, color = MaterialTheme.colorScheme.error) }
        Spacer(Modifier.height(8.dp)); TextButton(onClick = onBack) { Text("← 로그인으로") }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ResetScreen(api: DorawaApi, email: String, onDone: () -> Unit, onBack: () -> Unit) {
    val scope = rememberCoroutineScope()
    var code by remember { mutableStateOf("") }
    var pw by remember { mutableStateOf("") }
    var msg by remember { mutableStateOf("") }
    Column(Modifier.fillMaxSize().padding(24.dp).verticalScroll(rememberScrollState()),
        verticalArrangement = Arrangement.Center) {
        Text("비밀번호 재설정", style = MaterialTheme.typography.headlineMedium)
        Spacer(Modifier.height(8.dp))
        Text("이메일로 받은 코드와 새 비밀번호를 입력하세요.", style = MaterialTheme.typography.bodyMedium)
        Spacer(Modifier.height(16.dp))
        OutlinedTextField(code, { code = it }, label = { Text("6자리 코드") }, singleLine = true,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number), modifier = Modifier.fillMaxWidth())
        Spacer(Modifier.height(8.dp))
        OutlinedTextField(pw, { pw = it }, label = { Text("새 비밀번호") }, singleLine = true,
            visualTransformation = PasswordVisualTransformation(), modifier = Modifier.fillMaxWidth())
        Spacer(Modifier.height(16.dp))
        Button(onClick = {
            msg = ""
            scope.launch {
                try {
                    val r = api.reset(email, code.trim(), pw)
                    if (r.ok) { msg = "변경되었습니다. 로그인하세요."; onDone() }
                    else msg = r.error.ifEmpty { "재설정 실패" }
                } catch (e: Exception) { msg = "오류: ${e.message}" }
            }
        }, modifier = Modifier.fillMaxWidth()) { Text("비밀번호 변경") }
        if (msg.isNotEmpty()) { Spacer(Modifier.height(12.dp)); Text(msg, color = MaterialTheme.colorScheme.error) }
        Spacer(Modifier.height(8.dp)); TextButton(onClick = onBack) { Text("← 로그인으로") }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DeviceListScreen(api: DorawaApi, onOpen: (Device) -> Unit, onLogout: () -> Unit) {
    val scope = rememberCoroutineScope()
    var devices by remember { mutableStateOf<List<Device>>(emptyList()) }
    var msg by remember { mutableStateOf("불러오는 중...") }

    fun load() {
        scope.launch {
            try {
                devices = api.devices()
                msg = if (devices.isEmpty()) "연결된 기기가 없습니다." else ""
            } catch (e: Exception) { msg = "오류: ${e.message}" }
        }
    }
    LaunchedEffect(Unit) { load() }

    Scaffold(topBar = {
        TopAppBar(title = { Text("내 기기") }, actions = {
            TextButton(onClick = { load() }) { Text("새로고침") }
            TextButton(onClick = onLogout) { Text("로그아웃") }
        })
    }) { pad ->
        Column(Modifier.padding(pad).padding(16.dp).fillMaxSize()) {
            if (msg.isNotEmpty()) Text(msg, color = MaterialTheme.colorScheme.outline)
            devices.forEach { d ->
                Card(
                    onClick = { onOpen(d) },
                    modifier = Modifier.fillMaxWidth().padding(vertical = 6.dp)
                ) {
                    Row(Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
                        Text(d.name ?: "이름없음", style = MaterialTheme.typography.titleMedium)
                        Spacer(Modifier.weight(1f))
                        if (d.lost) Text("🚨 도난", color = MaterialTheme.colorScheme.error)
                    }
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DeviceDetailScreen(api: DorawaApi, device: Device, onBack: () -> Unit) {
    val scope = rememberCoroutineScope()
    var lost by remember { mutableStateOf(device.lost) }
    var reports by remember { mutableStateOf<List<Report>>(emptyList()) }
    var msg by remember { mutableStateOf("") }

    fun loadReports() {
        scope.launch {
            try { reports = api.reports(device.id) }
            catch (e: Exception) { msg = "보고 조회 오류: ${e.message}" }
        }
    }
    LaunchedEffect(Unit) { loadReports() }

    val fmt = remember { SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.KOREA) }

    Scaffold(topBar = {
        TopAppBar(
            title = { Text(device.name ?: "이름없음") },
            navigationIcon = { TextButton(onClick = onBack) { Text("← 목록") } },
            actions = { TextButton(onClick = { loadReports() }) { Text("새로고침") } }
        )
    }) { pad ->
        Column(
            Modifier.padding(pad).padding(16.dp).fillMaxSize().verticalScroll(rememberScrollState())
        ) {
            Button(
                onClick = {
                    val target = !lost
                    scope.launch {
                        try { api.setLost(device.id, target); lost = target }
                        catch (e: Exception) { msg = "오류: ${e.message}" }
                    }
                },
                colors = if (lost) ButtonDefaults.buttonColors()
                         else ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.error),
                modifier = Modifier.fillMaxWidth()
            ) { Text(if (lost) "✅ 도난 모드 끄기" else "🚨 도난 모드 켜기") }

            if (lost) {
                Spacer(Modifier.height(12.dp))
                Row(Modifier.fillMaxWidth()) {
                    Button(onClick = {
                        scope.launch {
                            try { api.capture(device.id, "photo"); msg = "📷 촬영 요청 보냄 (곧 올라옵니다)" }
                            catch (e: Exception) { msg = "오류: ${e.message}" }
                        }
                    }, modifier = Modifier.weight(1f)) { Text("📷 사진") }
                    Spacer(Modifier.width(8.dp))
                    Button(onClick = {
                        scope.launch {
                            try { api.capture(device.id, "video"); msg = "🎥 영상 요청 보냄 (곧 올라옵니다)" }
                            catch (e: Exception) { msg = "오류: ${e.message}" }
                        }
                    }, modifier = Modifier.weight(1f)) { Text("🎥 영상") }
                }
            }

            if (msg.isNotEmpty()) {
                Spacer(Modifier.height(8.dp)); Text(msg, color = MaterialTheme.colorScheme.outline)
            }

            Spacer(Modifier.height(16.dp))
            Text("최근 보고", style = MaterialTheme.typography.titleMedium)
            Spacer(Modifier.height(8.dp))
            if (reports.isEmpty()) Text("아직 보고가 없습니다.", color = MaterialTheme.colorScheme.outline)
            reports.forEach { r ->
                Card(Modifier.fillMaxWidth().padding(vertical = 4.dp)) {
                    Column(Modifier.padding(12.dp)) {
                        Text(fmt.format(Date((r.ts * 1000).toLong())),
                            style = MaterialTheme.typography.labelMedium,
                            color = MaterialTheme.colorScheme.outline)
                        Text("IP: ${r.publicIp ?: "?"} (${r.ipDesc ?: ""})")
                        if (r.lat != null)
                            Text("📍 위치: https://maps.google.com/?q=${r.lat},${r.lng}")
                        api.mediaUrl(r.photoUrl)?.let { Text("사진: $it") }
                        api.mediaUrl(r.videoUrl)?.let { Text("영상: $it") }
                    }
                }
            }
        }
    }
}
