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
  ${IfNot} ${isUpdated}
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

Function NonSystemDrivePageCreate
  ${If} ${isUpdated}
    Abort
  ${EndIf}
  StrCpy $R0 $WINDIR 2
  StrCpy $R1 $INSTDIR 2
  ${If} "$R0" != "$R1"
    Abort
  ${EndIf}
  nsDialogs::Create 1018
  Pop $NonSystemDrivePage
  ${If} $NonSystemDrivePage == error
    Abort
  ${EndIf}
  ${NSD_CreateLabel} 0 0 100% 48u "录音客户端不能安装在 Windows 系统盘。请返回上一步，选择 D:、E: 等非系统盘后继续。"
  Pop $NonSystemDriveLabel
  nsDialogs::Show
FunctionEnd

Function NonSystemDrivePageLeave
  MessageBox MB_ICONEXCLAMATION|MB_OK "请返回上一步并选择非系统盘安装目录。"
  Abort
FunctionEnd

!macro customPageAfterChangeDir
  Page custom NonSystemDrivePageCreate NonSystemDrivePageLeave
!macroend

!endif
