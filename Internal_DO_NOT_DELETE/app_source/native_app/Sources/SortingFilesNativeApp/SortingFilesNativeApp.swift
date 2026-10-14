import SwiftUI

@main
struct SortingFilesNativeApp: App {
    var body: some Scene {
        WindowGroup("Сортировка документов") {
            ContentView()
                .preferredColorScheme(.light)
                .environment(\.colorScheme, .light)
        }
        .windowResizability(.contentSize)
    }
}
