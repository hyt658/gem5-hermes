/*
 * Store to lines that loads send Hermes requests for, and check that every
 * load gets the newest data. Iteration i stores to line L(i), where L visits
 * each line once in a shuffled order, and then loads:
 *
 *  - the word it just stored, which comes from the store queue, while the
 *    Hermes read and the line fill for the store both go to memory
 *  - another word of the same line, which comes from memory and must not
 *    undo the store
 *  - line L(i - NEAR), which is dirty in L2 while DRAM still holds the old
 *    data, so its Hermes read gets old data and must be dropped
 *  - a random older line, which may be dirty in L3, waiting in the write
 *    queue of the memory controller, or back in DRAM
 *
 * It prints the number of wrong loads and exits with 1 if there are any.
 * Like pointer_chase.c, it uses no libc and must run in gem5:
 *
 *   gcc -O2 -static -nostdlib -fno-stack-protector -o store_test \
 *       store_test.c
 */

#define LINE_SIZE 64
#define LINE_WORDS (LINE_SIZE / sizeof(unsigned long))
#define NUM_LINES (1ul << 18) /* 16 MB */
#define NUM_ITERS (1ul << 17) /* fewer than NUM_LINES, so no line repeats */
/* far enough to leave L1, which holds 768 lines, but not L2 */
#define NEAR 2048

static unsigned long data[NUM_LINES][LINE_WORDS]
    __attribute__((aligned(LINE_SIZE)));

/* volatile keeps the compiler from removing, merging or hoisting accesses */
#define WORD(line, word) (*(volatile unsigned long *)&data[line][word])

/* print "<label> <value in hex>" */
#define PRINT(label, value) print_value(label " ", sizeof(label), value)

static unsigned long
next_random(void)
{
    static unsigned long state = 88172645463325252ul;

    state ^= state << 13;
    state ^= state >> 7;
    state ^= state << 17;
    return state;
}

static unsigned long
mix(unsigned long x)
{
    x *= 0x9e3779b97f4a7c15ul;
    x ^= x >> 32;
    x *= 0xff51afd7ed558ccdul;
    x ^= x >> 29;
    return x;
}

static unsigned long
init_value(unsigned long line)
{
    return mix(line + 1);
}

static unsigned long
store_value(unsigned long i)
{
    return mix(~i);
}

/* a bijection on line numbers, since each step is one */
static unsigned long
line_at(unsigned long i)
{
    unsigned long x = (i * 0x9e3779b1ul) & (NUM_LINES - 1);

    x ^= x >> 9;
    return (x * 0x85ebca6bul) & (NUM_LINES - 1);
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
store_main(void)
{
    unsigned long errors = 0;
    unsigned long sum = 0;
    unsigned long line;
    unsigned long i;

    /* word 6 is never stored to again, word 1 is stored to below */
    for (line = 0; line < NUM_LINES; line++)
        WORD(line, 6) = init_value(line);

    m5_reset_stats();

    for (i = 0; i < NUM_ITERS; i++) {
        unsigned long value = store_value(i);
        unsigned long x;
        unsigned long j;

        line = line_at(i);

        WORD(line, 1) = value;
        x = WORD(line, 1);
        errors += x != value;
        sum += x;

        x = WORD(line, 6);
        errors += x != init_value(line);
        sum += x;

        if (i >= NEAR) {
            x = WORD(line_at(i - NEAR), 1);
            errors += x != store_value(i - NEAR);
            sum += x;
        }

        if (i > 0) {
            j = next_random() % i;
            x = WORD(line_at(j), 1);
            errors += x != store_value(j);
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
        "call store_main\n");
