/*
 * Scan an array much larger than the LLC in order, and check that every load
 * gets the right data. A prefetcher catches this pattern, so its prefetch
 * reads race with the Hermes requests of the loads for the same lines:
 *
 *  - a prefetch read that reaches memory second takes over the Hermes read
 *  - a Hermes request that reaches memory second is dropped
 *  - a line the prefetcher already brought on chip leaves its Hermes read
 *    unused
 *
 * Word 0 of each line holds a known value and the other words are 0. It
 * prints the number of wrong loads and exits with 1 if there are any. Like
 * pointer_chase.c, it uses no libc and must run in gem5:
 *
 *   gcc -O2 -static -nostdlib -fno-stack-protector -o scan_test scan_test.c
 */

#define LINE_SIZE 64
#define LINE_WORDS (LINE_SIZE / sizeof(unsigned long))
#define NUM_LINES (1ul << 18) /* 16 MB */

static unsigned long data[NUM_LINES][LINE_WORDS]
    __attribute__((aligned(LINE_SIZE)));

/* volatile keeps the compiler from removing, merging or hoisting accesses */
#define WORD(line, word) (*(volatile unsigned long *)&data[line][word])

/* print "<label> <value in hex>" */
#define PRINT(label, value) print_value(label " ", sizeof(label), value)

static unsigned long
init_value(unsigned long line)
{
    unsigned long x = line + 1;

    x *= 0x9e3779b97f4a7c15ul;
    x ^= x >> 32;
    x *= 0xff51afd7ed558ccdul;
    x ^= x >> 29;
    return x;
}

static long
syscall3(long number, long arg0, long arg1, long arg2)
{
    long ret;

    __asm__ volatile("syscall"
                     : "=a"(ret)
                     : "a"(number), "D"(arg0), "S"(arg1), "d"(arg2)
                     : "rcx", "r11", "memory");
    return ret;
}

static void
m5_reset_stats(void)
{
    __asm__ volatile("xor %%edi, %%edi\n"
                     "xor %%esi, %%esi\n"
                     ".byte 0x0f, 0x04\n"
                     ".word 0x40\n"
                     : : : "rax", "rdi", "rsi", "memory");
}

static void
print_value(const char *label, unsigned long label_len, unsigned long value)
{
    static const char digits[] = "0123456789abcdef";
    char text[17];
    int i;

    for (i = 15; i >= 0; i--) {
        text[i] = digits[value & 0xf];
        value >>= 4;
    }
    text[16] = '\n';

    syscall3(1, 1, (long)label, label_len);
    syscall3(1, 1, (long)text, sizeof(text));
}

void
scan_main(void)
{
    unsigned long errors = 0;
    unsigned long sum = 0;
    unsigned long line;
    unsigned long word;

    for (line = 0; line < NUM_LINES; line++)
        WORD(line, 0) = init_value(line);

    m5_reset_stats();

    for (line = 0; line < NUM_LINES; line++) {
        for (word = 0; word < LINE_WORDS; word++) {
            unsigned long x = WORD(line, word);

            errors += x != (word == 0 ? init_value(line) : 0);
            sum += x;
        }
    }

    PRINT("sum", sum);
    PRINT("errors", errors);
    syscall3(231, errors != 0, 0, 0);
}

__asm__(".global _start\n"
        "_start:\n"
        "and $-16, %rsp\n"
        "call scan_main\n");
