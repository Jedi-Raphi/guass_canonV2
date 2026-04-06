;
; Copyright (c) 2020 Raspberry Pi (Trading) Ltd.
;
; SPDX-License-Identifier: BSD-3-Clause
;

.program Coil_handler
.side_set 1 opt
; Repeatedly get one word of data from the TX FIFO, stalling when the FIFO is
; empty. Write the least significant bit to the OUT pin group.
intit:
    wait   1 pin, 0
    set    pins, 1
    set    y, 0            side 1
    mov    y, !y
loop:
    in     pins, 1
    mov    x, isr
    jmp    !x, stop
    jmp    y--, loop
stop:
    set    pins, 0         side 0
    mov    isr, y
    push   noblock
    irq    nowait 0
end:
    jmp end

.program Timer
    set    y, 0
    mov    y, !y
timer_loop:
    jmp  pin detect [2]
    jmp y-- timer_loop 

    set    y, 0
    mov    y, !y
    irq 1
    jmp timer_loop

detect:
    irq 2
    mov    isr, y
    push   noblock
timer_loop_deac:
    in     pins, 1
    mov    x, isr
    jmp    !x, detect_deac
    jmp y-- timer_loop_deac

    set    y, 0
    mov    y, !y
    irq 1
    jmp timer_loop_deac

detect_deac:
    irq 3
    mov    isr, y
    push   noblock
    jmp timer_loop

% c-sdk {
%}





% c-sdk {

%}
