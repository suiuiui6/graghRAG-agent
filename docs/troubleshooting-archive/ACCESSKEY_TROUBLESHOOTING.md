# AccessKey配置问题排查

**错误信息:** SignatureDoesNotMatch

**原因:** AccessKey Secret不正确

---

## 当前配置

```
AccessKey ID: REDACTED_ACCESS_KEY_ID
AccessKey Secret: REDACTED_ACCESS_KEY_SECRET
```

---

## 如何获取正确的AccessKey

### 方法1：查看现有AccessKey

1. 登录阿里云控制台
2. 右上角头像 → **AccessKey管理**
3. 找到AccessKey ID为 `REDACTED_ACCESS_KEY_ID` 的记录
4. **问题：** Secret只在创建时显示一次，无法再次查看

### 方法2：创建新的AccessKey（推荐）

1. 登录阿里云控制台
2. 右上角头像 → **AccessKey管理**
3. 点击"创建AccessKey"
4. **立即复制并保存：**
   - AccessKey ID（例如：`<your-access-key-id>`）
   - AccessKey Secret（例如：`aBcDeFgHiJkLmNoPqRsTuVwXyZ123456`）
5. 将这两个值提供给我

---

## AccessKey格式说明

### AccessKey ID
- 格式：`LTAI` 开头
- 长度：约24个字符
- 示例：`REDACTED_ACCESS_KEY_ID`

### AccessKey Secret
- 格式：随机字符串（大小写字母+数字）
- 长度：约30个字符
- 示例：`aBcDeFgHiJkLmNoPqRsTuVwXyZ123456`
- **重要：** 只在创建时显示一次！

---

## 安全建议

### 使用RAM子账号（推荐）

不要使用主账号的AccessKey，创建RAM子账号：

1. 进入RAM控制台
2. 创建用户 → 选择"编程访问"
3. 添加权限：
   ```
   AliyunOSSFullAccess
   ```
   或自定义策略（只允许上传到特定bucket）
4. 保存AccessKey信息

### 自定义权限策略（最小权限）

```json
{
  "Version": "1",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "oss:PutObject",
        "oss:GetObject"
      ],
      "Resource": [
        "acs:oss:*:*:zhongshiyou-digitalization/graphrag/*"
      ]
    }
  ]
}
```

---

## 替代方案：使用公共读Bucket

如果不想使用AccessKey，可以：

1. 设置Bucket为"公共读"权限
2. 使用其他方式上传文件（OSS控制台、ossutil工具）
3. 在系统中使用URL模式上传

---

## 下一步

请提供：
1. **正确的AccessKey ID**
2. **正确的AccessKey Secret**

或者告诉我你想使用替代方案（公共读Bucket + URL上传）
