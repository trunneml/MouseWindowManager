#SingleInstance force
#Persistent

gridX := [0, 0.33, 0.5, 0.66, 1]
gridY := [0, 0.5, 1]

SetTimer,CheckIfAutoReloadNeeded,500
GoSub, ResetIt
Return


; Define your hotkey here and below!
LWin & LButton::
SetTimer, TrackIt, 50
return

; Define your hotkey here and above!
LWin & LButton Up::
SetTimer, TrackIt, Off
GoSub, MoveIt
GoSub, ResetIt
Return

TrackIt:
CoordMode, Mouse, Screen
MouseGetPos, curX, curY
minX := curX < minX ? curX : minX
minY := curY < minY ? curY : minY
maxX := curX > maxX ? curX : maxX
maxY := curY > maxY ? curY : maxY
return

MoveIt:
SysGet, MonitorCount, MonitorCount
Loop, %MonitorCount%
{
    SysGet, MonitorWorkArea, MonitorWorkArea, %A_Index%
    if (MonitorWorkAreaTop < minY && minY < MonitorWorkAreaBottom && MonitorWorkAreaLeft < minX && minX < MonitorWorkAreaRight) {
        MonitorPosX := MonitorWorkAreaLeft
        MonitorPosY := MonitorWorkAreaTop
        MonitorWidth := MonitorWorkAreaRight - MonitorWorkAreaLeft
        MonitorHeight := MonitorWorkAreaBottom - MonitorWorkAreaTop
        if (MonitorWidth > MonitorHeight) {
          MonitorGridX := gridX
          MonitorGridY := gridY
        } else {
          MonitorGridY := gridX
          MonitorGridX := gridY
        }

        for index, w in MonitorGridX {
          x1 := w * MonitorWidth + MonitorPosX
          x2 := MonitorGridX[index + 1] * MonitorWidth + MonitorPosX
          if (x2 > minX && x1 < minX) {
              newX := x1
          }
          if (x2 > maxX && x1 < maxX) {
              newW := x2 - newX
          }
        }
        for index, h in MonitorGridY {
          y1 := h * MonitorHeight + MonitorPosY
          y2 := MonitorGridY[index + 1] * MonitorHeight + MonitorPosY
          if (y2 > minY && y1 < minY) {
              newY := y1
          }
          if (y2 > maxY && y1 < maxY) {
              newH := y2 - newY
          }
        }
        WinRestore, A
        WinMove, A, , newX, newY, newW, newH
        if (newW == MonitorWidth && newH == MonitorHeight) {
          WinMaximize, A
        }
        break
    }
}
Return

ResetIt:
SysGet, VirtualScreenX, 76
SysGet, VirtualScreenY, 77
SysGet, VirtualScreenWidth, 78
SysGet, VirtualScreenHeight, 79

maxX := VirtualScreenX
minX := VirtualScreenX + VirtualScreenWidth
maxY := VirtualScreenY
minY := VirtualScreenY + VirtualScreenHeight
Return


CheckIfAutoReloadNeeded:
FileGetAttrib, attribs, %A_ScriptFullPath%
IfInString, attribs, A
{
    FileSetAttrib, -A, %A_ScriptFullPath%
    Reload
}
Return
