export function bindingErrorView(error = {}, context = {}) {
  const source = error || {};
  const operation = source.operation || "bind";
  const code = Number(source.businessCode);
  if (operation === "unbind") return unbindErrorView(code, context, source);
  return bindErrorView(code, context, source);
}

function bindErrorView(code, context, error) {
  if (error.unbound) {
    return {
      title: "原绑定已解除，新绑定未完成",
      detail: "设备已不再属于原班级或教室，暂时无法录音。",
      guidance: "请核对当前选择后重试新绑定；再次重试不会重复解绑。",
      primary: "replace",
      secondary: "reselect",
    };
  }
  if (code === 1) {
    return {
      title: "无法获取学校信息",
      detail: "当前登录信息中没有学校信息，暂时无法绑定设备。",
      guidance: "请重新登录后再选择班级或教室。",
      primary: "switch_identity",
    };
  }
  if (code === 2) {
    return {
      title: "未找到可用账号",
      detail: "当前登录手机号没有获取到可用的账号信息，暂时无法绑定设备。",
      guidance:
        "如果登录了错误手机号，请切换账号；如果手机号正确，请联系学校管理员确认该手机号已加入系统。",
      primary: "switch_identity",
    };
  }
  if (code === 3) {
    return {
      title: "当前学校不可用",
      detail: "系统未找到当前选择的学校，暂时无法绑定设备。",
      guidance: "请重新选择学校；如果学校选择正确，请联系学校管理员。",
      primary: "switch_identity",
    };
  }
  if ([4, 5, 6].includes(code)) {
    const content = {
      4: [
        "设备编号已被使用",
        "当前设备编号与系统中的已有记录冲突，暂时无法完成绑定。",
      ],
      5: ["班级信息异常", "当前选择的班级与学校信息不一致，暂时无法完成绑定。"],
      6: [
        "设备已绑定其他学校",
        "当前设备已归属于其他学校，无法在当前学校直接绑定。",
      ],
    }[code];
    return {
      title: content[0],
      detail: content[1],
      guidance: "请将本页面拍照并联系技术人员处理。",
      primary: "close",
      deviceNo: context.deviceNo || "",
      problemCode: `BIND-0${code}`,
    };
  }
  if (code === 7) {
    const target = context.className || context.classroom || "刚才选择的教室";
    return {
      title: "设备已绑定其他班级或教室",
      detail: `请确认刚才选择的“${target}”是否正确。`,
      guidance: "选择有误可以返回重新选择；确实需要更换，请执行换绑。",
      primary: "replace",
      secondary: "reselect",
      target,
    };
  }
  if (code === 8) {
    return {
      title: "尚未选择班级",
      detail: "本次绑定没有包含有效的班级信息。",
      guidance: "请返回并重新选择要绑定的班级。",
      primary: "reselect",
    };
  }
  if (code === 9) {
    return {
      title: "尚未填写教室名称",
      detail: "本次绑定没有包含有效的教室名称。",
      guidance: "请返回并填写要绑定的教室名称。",
      primary: "reselect",
    };
  }
  return {
    title: "绑定没有完成",
    detail: "客户端暂时无法完成设备绑定。",
    guidance: "请重新操作；仍无法完成时，请联系技术人员。",
    primary: "restart",
  };
}

function unbindErrorView(code, context, error) {
  if (code === 1) {
    const school = context.boundSchoolName || "设备所属学校";
    return {
      title: "无法确认解绑权限",
      detail: `当前登录信息中没有学校信息，设备尚未解除绑定。请使用“${school}”的账号重新登录。`,
      guidance: "重新登录后，需要再次确认解绑。",
      primary: "switch_identity",
    };
  }
  if (code === 2) {
    return {
      title: "设备记录异常",
      detail: "系统中未找到当前设备记录，解绑没有完成。",
      guidance: "请将本页面拍照并联系技术人员处理。",
      primary: "close",
      deviceNo: context.deviceNo || "",
      problemCode: "UNBIND-02",
    };
  }
  if (code === 3) {
    const bound = context.boundSchoolName || "设备所属学校";
    const current = context.currentSchoolName || "当前登录学校";
    return {
      title: "当前账号不能解绑此设备",
      detail: `这台设备属于“${bound}”，当前登录学校“${current}”无权解除绑定。`,
      guidance:
        "请切换到设备所属学校的账号；如果无法登录，请将本页面拍照并联系技术人员。",
      primary: "switch_identity",
      deviceNo: context.deviceNo || "",
    };
  }
  return {
    title: "解绑没有完成",
    detail: "客户端暂时无法完成设备解绑。",
    guidance: "设备绑定信息未清除，请稍后重新操作。",
    primary: "close",
  };
}
