export function authIssueView(auth, context = {}) {
  if (!auth) return null;
  if (auth.reason === "clock_invalid") {
    return {
      tone: "danger",
      title: "电脑时间不正确",
      description: "电脑时间与服务器不一致，暂时无法录音。",
      notice: "请校准为北京时间，完成后客户端会重新检测。",
      primary: "calibrate_clock",
      secondary: "open_clock_settings",
    };
  }
  if (auth.reason === "signature_invalid") {
    return {
      tone: "danger",
      title: "设备认证失败",
      description: "当前设备无法通过安全验证，暂时无法录音。",
      notice: "请将本页拍照并联系技术人员处理。",
      primary: "recheck_auth",
      deviceNo: context.deviceNo || "",
      problemCode: "AUTH-03",
    };
  }
  if (auth.rebindRequired) {
    const missingClass = auth.reason === "class_not_found";
    return {
      tone: "danger",
      title: missingClass ? "原班级或教室已不可用" : "设备需要重新绑定",
      description: "当前设备归属已失效，暂时无法录音。",
      notice: missingClass
        ? "请选择新的班级或教室完成绑定。"
        : "请重新完成设备初始化绑定。",
      primary: "bind",
      primaryLabel: missingClass ? "重新选择班级或教室" : "重新绑定设备",
    };
  }
  return null;
}
