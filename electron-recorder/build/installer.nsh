!include "LogicLib.nsh"
!include "nsDialogs.nsh"

!ifndef BUILD_UNINSTALLER

!macro TryFixedInstallDrive LETTER
  ${If} "$R9" == ""
    System::Call 'kernel32::GetDriveTypeW(w "${LETTER}:\\") i .r0'
    ${If} $0 == 3
      StrCpy $R1 $WINDIR 2
      ${If} "$R1" != "${LETTER}:"
        StrCpy $R9 "${LETTER}:"
      ${EndIf}
    ${EndIf}
  ${EndIf}
!macroend

!macro customInit
  StrCpy $R1 $WINDIR 2
  StrCpy $R2 $INSTDIR 2
  ${If} "$R1" == "$R2"
    StrCpy $R9 ""
    !insertmacro TryFixedInstallDrive "C"
    !insertmacro TryFixedInstallDrive "D"
    !insertmacro TryFixedInstallDrive "E"
    !insertmacro TryFixedInstallDrive "F"
    !insertmacro TryFixedInstallDrive "G"
    !insertmacro TryFixedInstallDrive "H"
    !insertmacro TryFixedInstallDrive "I"
    !insertmacro TryFixedInstallDrive "J"
    !insertmacro TryFixedInstallDrive "K"
    !insertmacro TryFixedInstallDrive "L"
    !insertmacro TryFixedInstallDrive "M"
    !insertmacro TryFixedInstallDrive "N"
    !insertmacro TryFixedInstallDrive "O"
    !insertmacro TryFixedInstallDrive "P"
    !insertmacro TryFixedInstallDrive "Q"
    !insertmacro TryFixedInstallDrive "R"
    !insertmacro TryFixedInstallDrive "S"
    !insertmacro TryFixedInstallDrive "T"
    !insertmacro TryFixedInstallDrive "U"
    !insertmacro TryFixedInstallDrive "V"
    !insertmacro TryFixedInstallDrive "W"
    !insertmacro TryFixedInstallDrive "X"
    !insertmacro TryFixedInstallDrive "Y"
    !insertmacro TryFixedInstallDrive "Z"
    ${If} "$R9" != ""
      StrCpy $INSTDIR "$R9\${APP_FILENAME}"
    ${EndIf}
  ${EndIf}
!macroend

Var NonSystemDrivePage
Var NonSystemDriveLabel
Var NonSystemDrivePath
Var NonSystemDriveBrowse

Function NonSystemDrivePageCreate
  StrCpy $R0 $WINDIR 2
  StrCpy $R1 $INSTDIR 2
  ${If} "$R0" == "$R1"
    StrCpy $R9 ""
    !insertmacro TryFixedInstallDrive "C"
    !insertmacro TryFixedInstallDrive "D"
    !insertmacro TryFixedInstallDrive "E"
    !insertmacro TryFixedInstallDrive "F"
    !insertmacro TryFixedInstallDrive "G"
    !insertmacro TryFixedInstallDrive "H"
    !insertmacro TryFixedInstallDrive "I"
    !insertmacro TryFixedInstallDrive "J"
    !insertmacro TryFixedInstallDrive "K"
    !insertmacro TryFixedInstallDrive "L"
    !insertmacro TryFixedInstallDrive "M"
    !insertmacro TryFixedInstallDrive "N"
    !insertmacro TryFixedInstallDrive "O"
    !insertmacro TryFixedInstallDrive "P"
    !insertmacro TryFixedInstallDrive "Q"
    !insertmacro TryFixedInstallDrive "R"
    !insertmacro TryFixedInstallDrive "S"
    !insertmacro TryFixedInstallDrive "T"
    !insertmacro TryFixedInstallDrive "U"
    !insertmacro TryFixedInstallDrive "V"
    !insertmacro TryFixedInstallDrive "W"
    !insertmacro TryFixedInstallDrive "X"
    !insertmacro TryFixedInstallDrive "Y"
    !insertmacro TryFixedInstallDrive "Z"
    ${If} "$R9" != ""
      StrCpy $INSTDIR "$R9\${APP_FILENAME}"
    ${EndIf}
  ${EndIf}

  nsDialogs::Create 1018
  Pop $NonSystemDrivePage
  ${If} $NonSystemDrivePage == error
    Abort
  ${EndIf}

  ${NSD_CreateLabel} 0 0 100% 28u "选择安装位置"
  Pop $NonSystemDriveLabel
  CreateFont $0 "Microsoft YaHei UI" 12 700
  SendMessage $NonSystemDriveLabel ${WM_SETFONT} $0 1

  ${NSD_CreateLabel} 0 32u 100% 28u "程序必须安装在非系统盘，以免学校电脑还原系统时被清除。已自动选择可用磁盘，你也可以更改。"
  Pop $NonSystemDriveLabel

  ${NSD_CreateText} 0 70u 76% 22u "$INSTDIR"
  Pop $NonSystemDrivePath
  SendMessage $NonSystemDrivePath ${EM_SETREADONLY} 1 0

  ${NSD_CreateButton} 79% 69u 21% 24u "更改位置"
  Pop $NonSystemDriveBrowse
  ${NSD_OnClick} $NonSystemDriveBrowse NonSystemDrivePageBrowse

  ${NSD_CreateLabel} 0 104u 100% 36u "请选择 D:、E:、F: 等本地固定磁盘。不能选择 Windows 所在磁盘、U 盘或网络位置。"
  Pop $NonSystemDriveLabel
  nsDialogs::Show
FunctionEnd

Function NonSystemDrivePageBrowse
  nsDialogs::SelectFolderDialog "选择非系统盘上的安装文件夹" "$INSTDIR"
  Pop $R0
  ${If} "$R0" != "error"
  ${AndIf} "$R0" != ""
    StrCpy $INSTDIR "$R0"
    ${NSD_SetText} $NonSystemDrivePath "$INSTDIR"
  ${EndIf}
FunctionEnd

Function NonSystemDrivePageLeave
  StrCpy $R0 $WINDIR 2
  StrCpy $R1 $INSTDIR 2
  System::Call 'kernel32::GetDriveTypeW(w "$R1\\") i .r2'
  ${If} "$R0" == "$R1"
    MessageBox MB_ICONEXCLAMATION|MB_OK "录音客户端不能安装在 Windows 系统盘，请选择 D:、E:、F: 等非系统盘。"
    Abort
  ${ElseIf} $2 != 3
    MessageBox MB_ICONEXCLAMATION|MB_OK "所选位置不是本地固定磁盘，请选择 D:、E:、F: 等非系统盘。"
    Abort
  ${EndIf}
FunctionEnd

!macro customPageAfterChangeDir
  Page custom NonSystemDrivePageCreate NonSystemDrivePageLeave
!macroend

!endif
