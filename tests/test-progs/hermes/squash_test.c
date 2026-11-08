/*
 * Make loads that issue a Hermes request and are then squashed, and check
 * that every load still gets the right data. It makes two kinds of squash:
 *
 *  - Branch misprediction: a branch depends on an off-chip load and resolves
 *    late, so by then the load on its wrong path has issued a Hermes request.
 *  - Memory order violation: a store gets its address late from an off-chip
 *    load, and a younger load to the same address runs before it.
 *
 * The stores write back the value a word already holds, so every load must
 * return the initial value of its word. It prints the number of wrong loads
 * and exits with 1 if there are any. Like pointer_chase.c, it uses no libc
 * and must run in gem5:
 *
 *   gcc -O2 -static -nostdlib -fno-stack-protector -o squash_test \
 *       squash_test.c
 */

#define LINE_SIZE 64
#define LINE_WORDS (LINE_SIZE / sizeof(unsigned long))
#define NUM_LINES (1ul << 18) /* 16 MB */
#define NUM_ITERS (1ul << 17)

static unsigned long data[NUM_LINES][LINE_WORDS]
    __attribute__((aligned(LINE_SIZE)));

/* volatile keeps the compiler from removing, merging or hoisting accesses */
#define WORD(line, word) (*(volatile unsigned long *)&data[line][word])

/* print "<label> <value in hex>" */
#define PRINT(label, value) print_value(label " ", sizeof(label), value)

#define INDEX(line, word) ((line) * LINE_WORDS + (word))

/*
 * In gem5 23, a 64-bit mov also waits for the old value of its destination,
 * and logical and shift instructions also wait for the old flags. Address
 * math after the test of v would then wait for v, and a wrong-path load
 * would never run, so the loop computes both indices before the test and
 * the loads take them as an index register.
 */
static inline unsigned long
load_index(unsigned long index)
{
    unsigned long x;

    __asm__ volatile("mov (%1,%2,8), %0"
                     : "=r"(x)
                     : "r"(&data[0][0]), "r"(index)
                     : "memory");
    return x;
}

static inline void
store_index(unsigned long index, unsigned long value)
{
    __asm__ volatile("mov %0, (%1,%2,8)"
                     :
                     : "r"(value), "r"(&data[0][0]), "r"(index)
                     : "memory");
}

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
init_value(unsigned long line, unsigned long word)
{
    unsigned long x = line * LINE_WORDS + word + 1;

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

static void
init_data(void)
{
    unsigned long line;
    unsigned long word;

    for (line = 0; line < NUM_LINES; line++)
        for (word = 0; word < 4; word++)
            WORD(line, word) = init_value(line, word);
}

void
squash_main(void)
{
    unsigned long errors = 0;
    unsigned long sum = 0;
    unsigned long i;

    init_data();
    m5_reset_stats();

    for (i = 0; i < NUM_ITERS; i++) {
        unsigned long r = next_random();
        unsigned long a = r % NUM_LINES;
        unsigned long b = (r >> 20) % NUM_LINES;
        unsigned long taken_index = INDEX(b, 1);
        unsigned long not_taken_index = INDEX(b ^ 1, 2);
        unsigned long v;
        unsigned long c;
        unsigned long x;

        /* keep both indices in registers before the test of v */
        __asm__ volatile("" : "+r"(taken_index), "+r"(not_taken_index));
        v = load_index(INDEX(a, 0));

        /*
         * v comes from memory and its low bit is random, so the branch is
         * often mispredicted and resolves late. The address b is ready
         * early, so the load on the wrong path runs and issues a Hermes
         * request before it is squashed.
         */
        if (v & 1) {
            x = load_index(taken_index);
            errors += x != init_value(b, 1);
        } else {
            x = load_index(not_taken_index);
            errors += x != init_value(b ^ 1, 2);
        }
        sum += x;

        /*
         * c is b or b ^ 2, picked by v, so the store address is known only
         * once v arrives. When it is b, the younger load has often run
         * already, and it is squashed and run again.
         */
        c = b ^ (v & 2);
        store_index(INDEX(c, 3), init_value(c, 3));
        x = load_index(INDEX(b, 3));
        errors += x != init_value(b, 3);
        sum += x;
    }

    PRINT("sum", sum);
    PRINT("errors", errors);
    syscall3(231, errors != 0, 0, 0);
}

__asm__(".global _start\n"
        "_start:\n"
        "and $-16, %rsp\n"
        "call squash_main\n");
