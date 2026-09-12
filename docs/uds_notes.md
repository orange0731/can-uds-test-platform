1. 核心服务 SID（今天先掌握 4 个）
SID	服务名	作用	正响应
0x10	DiagnosticSessionControl	切换诊断会话（默认/扩展）	0x50
0x22	ReadDataByIdentifier	按 DID 读数据（如读 VIN 码）	0x62
0x2E	WriteDataByIdentifier	按 DID 写数据	0x6E
0x27	SecurityAccess	安全解锁（种子&密钥）	0x67
2. 响应规则（铁律）
正响应 = SID + 0x40（如请求 0x22 → 响应 0x62）
负响应 = 0x7F + SID + NRC
3. 常见 NRC 负响应码
NRC	含义
 0x11	serviceNotSupported 服务不支持
0x13	incorrectMessageLength 报文长度错误
0x31	requestOutOfRange 请求超出范围（如DID不存在）
0x33	securityAccessDenied 安全访问被拒绝
经典 CAN ID 约定：诊断仪（Tester）请求发 0x7E0，ECU 响应回 0x7E8。