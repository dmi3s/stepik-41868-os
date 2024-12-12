.data
msg:
    .ascii "Hello, world!\n"
    len = . - msg      # символу len присваивается длина строки

.text
    .global _start     # точка входа в программу
_start:
    mov   $2,%rdi
    mov   $11,%rsi
    call  pow
    movl  $4, %eax     # системный вызов № 4 — sys_write
    movl  $1, %ebx     # поток № 1 — stdout
    movl  $msg, %ecx   # указатель на выводимую строку
    movl  $len, %edx   # длина строки
    int   $0x80        # вызов ядра

    movl  $1, %eax     # системный вызов № 1 — sys_exit
    xorl  %ebx, %ebx   # выход с кодом 0
    int   $0x80        # вызов ядра
    

// x - rdi
// p - rsi
// result = rax
pow:
    mov $1,%rax 

.mul_rep:
    test %rsi,%rsi
    jz .return
    test $1,%rsi
    jz .even
    imul %rdi

.even:
    imul %rdi,%rdi
    shr $1,%rsi
    jmp .mul_rep
    
.return:
    retq
    