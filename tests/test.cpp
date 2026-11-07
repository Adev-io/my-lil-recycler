// test.cpp: checks the core with plain asserts. Run: make test
// Author: Ari Klopfer / A_Development. MIT
#include "check.h"
#include "test_audio.h"
#include "test_analysis.h"
#include "test_transport.h"
#include "test_library.h"
#include "test_file.h"
#include "test_picker.h"
#include "test_stretch.h"
#include "test_deck.h"
#include "test_shape.h"
#include "test_view.h"
#include "test_stutter.h"

int main()
{
    testAudio();
    testAnalysis();
    testTransport();
    testLibrary();
    testFile();
    testPicker();
    testStretch();
    testDeck();
    testShape();
    testView();
    testStutter();
    std::printf ("%s: %d failure(s)\n", failures ? "FAILED" : "passed", failures);
    return failures ? 1 : 0;
}
