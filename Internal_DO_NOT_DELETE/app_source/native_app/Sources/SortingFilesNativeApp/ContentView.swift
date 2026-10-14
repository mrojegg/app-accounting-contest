import SwiftUI

struct ContentView: View {
    @StateObject private var state: AppState
    private let logViewportHeight: CGFloat = 220

    @MainActor
    init(state: AppState) {
        _state = StateObject(wrappedValue: state)
    }

    @MainActor
    init() {
        _state = StateObject(wrappedValue: AppState())
    }

    var body: some View {
        GeometryReader { proxy in
            VStack(spacing: 0) {
                appToolbar

                Divider()
                    .overlay(AppPalette.stroke)

                HStack(spacing: 0) {
                    operationSidebar

                    Divider()
                        .overlay(AppPalette.stroke)

                    ScrollView(.vertical, showsIndicators: true) {
                        mainContent(maxWidth: contentMaxWidth(for: proxy.size.width - 502))
                    }
                    .background(AppChromeBackground())

                    Divider()
                        .overlay(AppPalette.stroke)

                    runInspector
                }
            }
            .background(AppPalette.panel)
            .foregroundStyle(AppPalette.textPrimary)
            .tint(AppPalette.accent)
        }
        .frame(minWidth: 1240, minHeight: 760)
        .alert("Ошибка", isPresented: Binding(
            get: { state.errorMessage != nil && !state.isShowingSettings },
            set: { if !$0 { state.errorMessage = nil } }
        )) {
            Button("OK") { state.errorMessage = nil }
        } message: {
            Text(state.errorMessage ?? "")
        }
        .sheet(isPresented: $state.isShowingSettings) {
            SettingsRootView(state: state)
                .preferredColorScheme(.light)
                .environment(\.colorScheme, .light)
        }
        .onAppear {
            state.refreshManualReviewItems()
        }
        .onChange(of: state.resultArchivePath) { _ in
            state.refreshManualReviewItems()
        }
        .onChange(of: state.manualReviewCount) { _ in
            state.refreshManualReviewItems()
        }
    }

    private var shouldShowLog: Bool {
        state.isRunning || !state.logText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
    }

    private func contentMaxWidth(for windowWidth: CGFloat) -> CGFloat {
        min(max(windowWidth - 48, 0), 1120)
    }

    private func mainContent(maxWidth: CGFloat) -> some View {
        VStack(alignment: .leading, spacing: 18) {
            parametersSection
            salaryExcelSection
            manualReviewSection(maxWidth: maxWidth)
            if shouldShowLog {
                logSection
            }
        }
        .padding(.horizontal, 24)
        .padding(.vertical, 22)
        .frame(maxWidth: maxWidth, alignment: .leading)
        .frame(maxWidth: .infinity, alignment: .center)
    }

    private var appToolbar: some View {
        HStack(spacing: 12) {
            ZStack {
                RoundedRectangle(cornerRadius: 7, style: .continuous)
                    .fill(AppPalette.accent)
                Image(systemName: "doc.text.magnifyingglass")
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundStyle(Color.white)
            }
            .frame(width: 32, height: 32)

            Text("Сортировка документов")
                .font(.system(size: 16, weight: .semibold))
                .foregroundStyle(AppPalette.textPrimary)

            Rectangle()
                .fill(AppPalette.stroke)
                .frame(width: 1, height: 18)

            Label(state.runOperation.title, systemImage: operationIcon(state.runOperation))
                .font(.system(size: 12, weight: .medium))
                .foregroundStyle(AppPalette.textSecondary)

            Spacer()

            AppPill(
                title: state.isRunning ? "Выполняется" : "Готово к работе",
                systemImage: state.isRunning ? "bolt.fill" : "checkmark.circle.fill",
                tone: state.isRunning ? .accent : .success
            )
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 10)
        .background(AppPalette.panel)
    }

    private var operationSidebar: some View {
        VStack(alignment: .leading, spacing: 0) {
            Text("ОПЕРАЦИИ")
                .font(.system(size: 11, weight: .semibold))
                .foregroundStyle(AppPalette.sidebarTextSecondary)
                .padding(.horizontal, 12)
                .padding(.bottom, 8)

            VStack(spacing: 5) {
                ForEach(RunOperation.allCases) { operation in
                    operationSidebarButton(operation)
                }
            }

            if state.runOperation == .sorting || state.runOperation == .mergePDF {
                Divider()
                    .overlay(AppPalette.sidebarStroke)
                    .padding(.vertical, 16)

                Text("РЕЖИМ")
                    .font(.system(size: 11, weight: .semibold))
                    .foregroundStyle(AppPalette.sidebarTextSecondary)
                    .padding(.horizontal, 12)
                    .padding(.bottom, 8)

                VStack(spacing: 5) {
                    ForEach(SortMode.allCases) { mode in
                        sidebarModeButton(mode)
                    }
                }
            }

            Spacer(minLength: 18)

            Button {
                state.selectedSettingsSection = .admin
                state.openSettings()
            } label: {
                HStack(spacing: 10) {
                    ZStack {
                        RoundedRectangle(cornerRadius: 6, style: .continuous)
                            .fill(Color.white.opacity(0.10))
                        Image(systemName: "book.closed.fill")
                            .font(.system(size: 13, weight: .semibold))
                    }
                    .frame(width: 30, height: 30)

                    VStack(alignment: .leading, spacing: 2) {
                        Text("Гайд")
                            .font(.system(size: 13, weight: .semibold))
                        Text("Работа с приложением")
                            .font(.system(size: 10, weight: .medium))
                            .foregroundStyle(AppPalette.sidebarTextSecondary)
                    }

                    Spacer(minLength: 0)

                    Image(systemName: "chevron.right")
                        .font(.system(size: 10, weight: .bold))
                        .foregroundStyle(AppPalette.sidebarTextSecondary)
                }
                .foregroundStyle(AppPalette.sidebarText)
                .padding(.horizontal, 10)
                .frame(height: 50)
                .background(
                    RoundedRectangle(cornerRadius: 7, style: .continuous)
                        .fill(AppPalette.sidebarRaised)
                        .overlay(
                            RoundedRectangle(cornerRadius: 7, style: .continuous)
                                .stroke(AppPalette.sidebarStroke, lineWidth: 1)
                        )
                )
            }
            .buttonStyle(.plain)
            .padding(.bottom, 10)

            VStack(alignment: .leading, spacing: 8) {
                HStack(spacing: 8) {
                    Circle()
                        .fill(state.isRunning ? AppPalette.warning : AppPalette.success)
                        .frame(width: 7, height: 7)
                    Text(state.isRunning ? "Выполняется" : "Система готова")
                        .font(.system(size: 12, weight: .semibold))
                        .foregroundStyle(AppPalette.sidebarText)
                }

                if state.manualReviewCount > 0 {
                    Label("Ручная проверка: \(state.manualReviewCount)", systemImage: "exclamationmark.triangle.fill")
                        .font(.system(size: 12, weight: .medium))
                        .foregroundStyle(Color(red: 0.984, green: 0.753, blue: 0.329))
                }
            }
            .padding(12)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(
                RoundedRectangle(cornerRadius: 7, style: .continuous)
                    .fill(AppPalette.sidebarRaised)
            )
        }
        .padding(12)
        .frame(width: 232)
        .frame(maxHeight: .infinity, alignment: .top)
        .background(AppPalette.sidebar)
    }

    private func operationSidebarButton(_ operation: RunOperation) -> some View {
        let isSelected = state.runOperation == operation
        return Button {
            state.runOperation = operation
        } label: {
            HStack(spacing: 10) {
                Image(systemName: operationIcon(operation))
                    .font(.system(size: 14, weight: .semibold))
                    .frame(width: 20)
                Text(operation.title)
                    .font(.system(size: 13, weight: .semibold))
                    .lineLimit(1)
                Spacer(minLength: 0)
            }
            .foregroundStyle(isSelected ? AppPalette.sidebarText : AppPalette.sidebarTextSecondary)
            .padding(.horizontal, 11)
            .frame(height: 40)
            .background(
                RoundedRectangle(cornerRadius: 7, style: .continuous)
                    .fill(isSelected ? AppPalette.sidebarSelection : Color.clear)
            )
            .overlay(alignment: .leading) {
                if isSelected {
                    RoundedRectangle(cornerRadius: 2, style: .continuous)
                        .fill(Color(red: 0.408, green: 0.820, blue: 0.722))
                        .frame(width: 3, height: 20)
                        .padding(.leading, 2)
                }
            }
        }
        .buttonStyle(.plain)
    }

    private func sidebarModeButton(_ mode: SortMode) -> some View {
        let isSelected = state.mode == mode
        return Button {
            state.mode = mode
        } label: {
            HStack(spacing: 10) {
                Image(systemName: mode == .copy ? "doc.on.doc" : "arrow.right")
                    .font(.system(size: 13, weight: .semibold))
                    .frame(width: 20)
                Text(mode.title)
                    .font(.system(size: 13, weight: .medium))
                Spacer(minLength: 0)
                if isSelected {
                    Image(systemName: "checkmark")
                        .font(.system(size: 11, weight: .bold))
                }
            }
            .foregroundStyle(isSelected ? AppPalette.sidebarText : AppPalette.sidebarTextSecondary)
            .padding(.horizontal, 11)
            .frame(height: 36)
            .background(
                RoundedRectangle(cornerRadius: 7, style: .continuous)
                    .fill(isSelected ? AppPalette.sidebarRaised : Color.clear)
            )
        }
        .buttonStyle(.plain)
    }

    private var runInspector: some View {
        VStack(alignment: .leading, spacing: 14) {
            inspectorSectionLabel("СОСТОЯНИЕ")

            HStack(spacing: 9) {
                ZStack {
                    Circle()
                        .fill(state.isRunning ? AppPalette.warningMuted : AppPalette.successMuted)
                    Circle()
                        .fill(state.isRunning ? AppPalette.warning : AppPalette.success)
                        .frame(width: 8, height: 8)
                }
                .frame(width: 22, height: 22)

                VStack(alignment: .leading, spacing: 2) {
                    Text(state.isRunning ? "Обработка" : "Готово к запуску")
                        .font(.system(size: 13, weight: .semibold))
                        .foregroundStyle(AppPalette.textPrimary)
                    Text(state.currentPhaseText)
                        .font(.system(size: 11, weight: .medium))
                        .foregroundStyle(AppPalette.textSecondary)
                        .lineLimit(1)
                }
            }

            ProgressView(value: state.progressValue, total: 100)
                .tint(AppPalette.accent)

            HStack {
                Text(state.statusText)
                    .font(.system(size: 12, weight: .medium))
                    .foregroundStyle(AppPalette.textSecondary)
                    .lineLimit(2)
                Spacer(minLength: 8)
                Text(state.progressText)
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundStyle(AppPalette.textPrimary)
                    .monospacedDigit()
            }

            Divider()
                .overlay(AppPalette.stroke)

            inspectorSectionLabel("ДЕЙСТВИЯ")

            primaryRunButton

            Button {
                state.stopSorting()
            } label: {
                Label("Остановить", systemImage: "stop.fill")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(AppDestructiveButtonStyle())
            .disabled(!state.isRunning)

            if state.runOperation == .sorting && !state.resultArchivePath.isEmpty {
                Button {
                    state.startManualReviewReprocess()
                } label: {
                    Label("Дообработать", systemImage: "tray.and.arrow.down")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(AppSecondaryButtonStyle())
                .disabled(state.isRunning || state.manualReviewCount == 0)
            }

            if state.runOperation == .salaryExcel && !state.salaryUnknownEmployees.isEmpty {
                Button {
                    state.startSalaryExcelFinalize()
                } label: {
                    Label("Сохранить и создать", systemImage: "checkmark.circle")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(AppSecondaryButtonStyle())
                .disabled(state.isRunning || !state.salaryAllUnknownAssigned)
            }

            Divider()
                .overlay(AppPalette.stroke)

            inspectorSectionLabel("РЕЗУЛЬТАТ")

            VStack(alignment: .leading, spacing: 8) {
                if state.manualReviewCount > 0 {
                    AppPill(title: "Ручная проверка: \(state.manualReviewCount)", systemImage: "exclamationmark.triangle", tone: .warning)
                }
                if state.unresolvedCount > 0 {
                    AppPill(title: "Не распределено: \(state.unresolvedCount)", systemImage: "questionmark.folder", tone: .danger)
                }
                if state.resultArchivePath.isEmpty && state.manualReviewCount == 0 && state.unresolvedCount == 0 {
                    Text("Результат появится после обработки")
                        .font(.system(size: 12, weight: .medium))
                        .foregroundStyle(AppPalette.textSecondary)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }

            if !state.resultArchivePath.isEmpty {
                if !state.completionReportSummary.isEmpty {
                    Text(state.completionReportSummary)
                        .font(.system(size: 12))
                        .foregroundStyle(AppPalette.textSecondary)
                        .fixedSize(horizontal: false, vertical: true)
                    Button { state.openCompletionReport() } label: {
                        Label("Итог обработки", systemImage: "checklist")
                    }
                    .buttonStyle(AppSecondaryButtonStyle())
                }
                Button {
                    state.openResultFolder()
                } label: {
                    Label("Открыть результат", systemImage: "folder")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(AppSecondaryButtonStyle())
            }

            if state.manualReviewCount > 0 {
                Button {
                    state.openManualReviewReport()
                } label: {
                    Label("Отчет проверки", systemImage: "doc.text.magnifyingglass")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(AppSecondaryButtonStyle())
            }

            Divider()
                .overlay(AppPalette.stroke)

            HStack {
                inspectorSectionLabel("ЖУРНАЛ")
                Spacer()
                Button {
                    state.copyLog()
                } label: {
                    Image(systemName: "doc.on.clipboard")
                }
                .buttonStyle(AppToolbarIconButtonStyle())
                .help("Скопировать журнал")

                Button {
                    state.clearLog()
                } label: {
                    Image(systemName: "trash")
                }
                .buttonStyle(AppToolbarIconButtonStyle(isDestructive: true))
                .help("Очистить журнал")
            }

            Spacer(minLength: 0)
        }
        .padding(16)
        .frame(width: 270)
        .frame(maxHeight: .infinity, alignment: .top)
        .background(AppPalette.panelRaised)
    }

    private func inspectorSectionLabel(_ title: String) -> some View {
        Text(title)
            .font(.system(size: 11, weight: .semibold))
            .foregroundStyle(AppPalette.textSecondary)
    }

    private var parametersSection: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(spacing: 14) {
                ZStack {
                    RoundedRectangle(cornerRadius: 8, style: .continuous)
                        .fill(AppPalette.accent)
                    Image(systemName: operationIcon(state.runOperation))
                        .font(.system(size: 19, weight: .semibold))
                        .foregroundStyle(Color.white)
                }
                .frame(width: 46, height: 46)

                VStack(alignment: .leading, spacing: 3) {
                    Text(state.runOperation.title)
                        .font(.system(size: 22, weight: .semibold))
                        .foregroundStyle(AppPalette.textPrimary)
                    Text("МАРШРУТ ОБРАБОТКИ")
                        .font(.system(size: 10, weight: .bold))
                        .foregroundStyle(AppPalette.textSecondary)
                }

                Spacer()

                if state.runOperation == .sorting || state.runOperation == .mergePDF {
                    AppPill(title: state.mode.title, systemImage: state.mode == .copy ? "doc.on.doc" : "arrow.right", tone: .accent)
                }
            }
            .padding(18)

            Divider()
                .overlay(AppPalette.stroke)

            VStack(spacing: 0) {
                sourceRouteStep

                if state.runOperation != .mergePDF {
                    routeConnector

                    routeStep(number: "02", icon: "folder.badge.plus", title: "Папка назначения") {
                        TextField(outputFolderPlaceholder, text: $state.outputFolder)
                            .appField()
                    } action: {
                        Button("Выбрать") { state.chooseOutputFolder() }
                            .buttonStyle(AppSecondaryButtonStyle())
                    }

                    if state.runOperation == .sorting {
                        routeConnector
                        routeStep(number: "03", icon: "textformat", title: "Имя итоговой папки") {
                            TextField("Имя архива результата", text: $state.archiveName)
                                .appField()
                        } action: {
                            Button("Подставить") { state.fillArchiveNameFromSource() }
                                .buttonStyle(AppSecondaryButtonStyle())
                        }
                    }
                }
            }
            .padding(18)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .fill(AppPalette.panel)
                .overlay(
                    RoundedRectangle(cornerRadius: 8, style: .continuous)
                        .stroke(AppPalette.stroke, lineWidth: 1)
                )
        )
        .shadow(color: AppPalette.shadow, radius: 5, x: 0, y: 2)
    }

    @ViewBuilder
    private var sourceRouteStep: some View {
        if state.runOperation == .sorting {
            routeStep(number: "01", icon: "folder", title: "Исходная папка") {
                TextField("Папка с исходными файлами", text: $state.sourceFolder)
                    .appField()
            } action: {
                Button("Выбрать") { state.chooseSourceFolder() }
                    .buttonStyle(AppSecondaryButtonStyle())
            }
        } else if state.runOperation == .splitPDF {
            routeStep(number: "01", icon: "doc", title: "PDF файл") {
                TextField("Большой PDF для разбиения", text: $state.sourcePDFFile)
                    .appField()
            } action: {
                Button("Выбрать") { state.chooseSourcePDFFile() }
                    .buttonStyle(AppSecondaryButtonStyle())
            }
        } else if state.runOperation == .mergePDF {
            routeStep(number: "01", icon: "doc.on.doc", title: "Папка с PDF") {
                TextField("Папка с PDF для объединения", text: $state.sourceFolder)
                    .appField()
            } action: {
                Button("Выбрать") { state.chooseSourceFolder() }
                    .buttonStyle(AppSecondaryButtonStyle())
            }
        } else {
            routeStep(number: "01", icon: "tablecells", title: "Excel ведомости") {
                Text(state.salaryExcelFiles.isEmpty ? "Файлы не выбраны" : "\(state.salaryExcelFiles.count) файлов выбрано")
                    .font(.system(size: 13, weight: .medium))
                    .foregroundStyle(state.salaryExcelFiles.isEmpty ? AppPalette.textSecondary : AppPalette.textPrimary)
                    .lineLimit(1)
                    .truncationMode(.middle)
                    .frame(maxWidth: .infinity, minHeight: 18, alignment: .leading)
                    .padding(.horizontal, 11)
                    .padding(.vertical, 9)
                    .background(
                        RoundedRectangle(cornerRadius: 7, style: .continuous)
                            .fill(AppPalette.panel)
                            .overlay(
                                RoundedRectangle(cornerRadius: 7, style: .continuous)
                                    .stroke(AppPalette.strongStroke.opacity(0.66), lineWidth: 1)
                            )
                    )
            } action: {
                Button("Выбрать") { state.chooseSalaryExcelFiles() }
                    .buttonStyle(AppSecondaryButtonStyle())
            }
        }
    }

    private var routeConnector: some View {
        HStack(spacing: 0) {
            Rectangle()
                .fill(AppPalette.stroke)
                .frame(width: 1, height: 12)
        }
        .frame(width: 42, height: 20)
    }

    private func routeStep<Content: View, Action: View>(
        number: String,
        icon: String,
        title: String,
        @ViewBuilder content: () -> Content,
        @ViewBuilder action: () -> Action
    ) -> some View {
        HStack(spacing: 14) {
            ZStack {
                RoundedRectangle(cornerRadius: 7, style: .continuous)
                    .fill(AppPalette.accentMuted)
                Image(systemName: icon)
                    .font(.system(size: 15, weight: .semibold))
                    .foregroundStyle(AppPalette.accent)
            }
            .frame(width: 42, height: 42)
            .overlay(alignment: .topTrailing) {
                Text(number)
                    .font(.system(size: 8, weight: .bold))
                    .foregroundStyle(Color.white)
                    .frame(width: 17, height: 17)
                    .background(Circle().fill(AppPalette.accent))
                    .offset(x: 5, y: -5)
            }

            Text(title)
                .font(.system(size: 12, weight: .semibold))
                .foregroundStyle(AppPalette.textSecondary)
                .frame(width: 132, alignment: .leading)

            content()
                .frame(maxWidth: .infinity)

            action()
                .frame(minWidth: 94)
        }
        .padding(14)
        .background(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .fill(AppPalette.panelRaised)
                .overlay(
                    RoundedRectangle(cornerRadius: 8, style: .continuous)
                        .stroke(AppPalette.stroke.opacity(0.75), lineWidth: 1)
                )
        )
    }

    private var outputFolderPlaceholder: String {
        switch state.runOperation {
        case .sorting:
            return "Куда положить итоговый архив"
        case .splitPDF:
            return "Куда положить отдельные PDF"
        case .mergePDF:
            return "Куда положить объединенный PDF"
        case .salaryExcel:
            return "Куда положить таблицы по офисам"
        }
    }

    private var operationPicker: some View {
        HStack(spacing: 3) {
            ForEach(RunOperation.allCases) { item in
                segmentedButton(
                    title: item.title,
                    systemImage: operationIcon(item),
                    isSelected: state.runOperation == item
                ) {
                    state.runOperation = item
                }
            }
        }
        .padding(3)
        .background(segmentedBackground)
    }

    private var modePicker: some View {
        HStack(spacing: 3) {
            ForEach(SortMode.allCases) { item in
                segmentedButton(
                    title: item.title,
                    systemImage: item == .copy ? "doc.on.doc" : "arrow.right",
                    isSelected: state.mode == item
                ) {
                    state.mode = item
                }
            }
        }
        .padding(3)
        .background(segmentedBackground)
    }

    private var segmentedBackground: some View {
        RoundedRectangle(cornerRadius: 8, style: .continuous)
            .fill(AppPalette.panelMuted)
            .overlay(
                RoundedRectangle(cornerRadius: 8, style: .continuous)
                    .stroke(AppPalette.stroke, lineWidth: 1)
            )
    }

    private func segmentedButton(title: String, systemImage: String? = nil, isSelected: Bool, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            HStack(spacing: 6) {
                if let systemImage {
                    Image(systemName: systemImage)
                        .font(.system(size: 12, weight: .semibold))
                }
                Text(title)
                    .lineLimit(1)
            }
                .font(.system(size: 13, weight: .semibold))
                .foregroundStyle(isSelected ? AppPalette.accent : AppPalette.textSecondary)
                .frame(maxWidth: .infinity)
                .padding(.horizontal, 12)
                .padding(.vertical, 7)
                .background(
                    RoundedRectangle(cornerRadius: 6, style: .continuous)
                        .fill(isSelected ? AppPalette.accentMuted : Color.clear)
                        .overlay(
                            RoundedRectangle(cornerRadius: 6, style: .continuous)
                                .stroke(isSelected ? AppPalette.accent.opacity(0.25) : Color.clear, lineWidth: 1)
                        )
                )
        }
        .buttonStyle(.plain)
    }

    private func operationIcon(_ operation: RunOperation) -> String {
        switch operation {
        case .sorting: return "arrow.triangle.branch"
        case .splitPDF: return "doc.on.doc"
        case .mergePDF: return "doc.richtext"
        case .salaryExcel: return "tablecells"
        }
    }

    private var manualReviewTypePicker: some View {
        Picker("Тип документа", selection: $state.manualReviewType) {
            ForEach(ManualReviewType.allCases) { item in
                Text(item.rawValue).tag(item)
            }
        }
        .labelsHidden()
        .pickerStyle(.menu)
        .frame(maxWidth: .infinity, alignment: .leading)
        .onChange(of: state.manualReviewType) { _ in
            state.syncManualReviewDefaultsFromType()
        }
    }

    @ViewBuilder
    private var primaryRunButton: some View {
        if state.runOperation == .sorting {
            Button {
                state.startSorting()
            } label: {
                Label("Сортировать", systemImage: "arrow.triangle.branch")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(AppPrimaryButtonStyle())
            .disabled(state.isRunning)
        } else if state.runOperation == .splitPDF {
            Button {
                state.startPDFSplit()
            } label: {
                Label("Разбить PDF", systemImage: "doc.on.doc")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(AppPrimaryButtonStyle())
            .disabled(state.isRunning)
        } else if state.runOperation == .mergePDF {
            Button {
                state.startPDFMerge()
            } label: {
                Label("Объединить PDF", systemImage: "doc.richtext")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(AppPrimaryButtonStyle())
            .disabled(state.isRunning)
        } else {
            Button {
                state.startSalaryExcelAnalyze()
            } label: {
                Label("Проверить ведомости", systemImage: "tablecells")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(AppPrimaryButtonStyle())
            .disabled(state.isRunning || state.salaryExcelFiles.isEmpty)
        }
    }

    private var commandBar: some View {
        WrappingHStack(horizontalSpacing: 8, verticalSpacing: 8) {
            if state.runOperation == .sorting && !state.resultArchivePath.isEmpty {
                Button {
                    state.startManualReviewReprocess()
                } label: {
                    Label("Дообработать", systemImage: "tray.and.arrow.down")
                }
                .buttonStyle(AppSecondaryButtonStyle())
                .disabled(state.isRunning || state.manualReviewCount == 0)
            }

            if state.runOperation == .salaryExcel && !state.salaryUnknownEmployees.isEmpty {
                Button {
                    state.startSalaryExcelFinalize()
                } label: {
                    Label("Сохранить и создать", systemImage: "checkmark.circle")
                }
                .buttonStyle(AppSecondaryButtonStyle())
                .disabled(state.isRunning || !state.salaryAllUnknownAssigned)
            }

            Button {
                state.clearLog()
            } label: {
                Label("Очистить лог", systemImage: "xmark.circle")
            }
            .buttonStyle(AppSecondaryButtonStyle())

            Button {
                state.copyLog()
            } label: {
                Label("Скопировать лог", systemImage: "doc.on.clipboard")
            }
            .buttonStyle(AppSecondaryButtonStyle())

            if !state.resultArchivePath.isEmpty {
                Button {
                    state.openResultFolder()
                } label: {
                    Label("Открыть результат", systemImage: "folder")
                }
                .buttonStyle(AppSecondaryButtonStyle())
            }

            if state.manualReviewCount > 0 {
                Button {
                    state.openManualReviewReport()
                } label: {
                    Label("Отчет проверки", systemImage: "doc.text.magnifyingglass")
                }
                .buttonStyle(AppSecondaryButtonStyle())
            }
        }
    }

    private var progressSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 12) {
                AppSectionHeader("Ход выполнения", systemImage: "gauge")
                Text(state.statusText)
                    .font(.system(size: 13, weight: .medium))
                    .foregroundStyle(AppPalette.textSecondary)
                    .lineLimit(1)
                Spacer()
                Text(state.progressText)
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundStyle(AppPalette.textPrimary)
                    .monospacedDigit()
            }

            ProgressView(value: state.progressValue, total: 100)
                .tint(AppPalette.accent)
                .scaleEffect(x: 1, y: 1.05, anchor: .center)

            HStack(spacing: 8) {
                AppPill(title: state.isRunning ? "Обработка" : "Готов к запуску", systemImage: state.isRunning ? "bolt.fill" : "checkmark.circle", tone: state.isRunning ? .accent : .success)
                if state.manualReviewCount > 0 {
                    AppPill(title: "Ручная проверка: \(state.manualReviewCount)", systemImage: "exclamationmark.bubble", tone: .warning)
                }
                if state.unresolvedCount > 0 {
                    AppPill(title: "Не распределено: \(state.unresolvedCount)", systemImage: "questionmark.folder", tone: .danger)
                }
                Spacer()
            }

            Divider()
                .overlay(AppPalette.stroke)

            commandBar
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .appCard()
    }

    @ViewBuilder
    private var salaryExcelSection: some View {
        if state.runOperation == .salaryExcel && (!state.salaryUnknownEmployees.isEmpty || !state.salaryCreatedFiles.isEmpty || !state.salarySummaryText.isEmpty) {
            VStack(alignment: .leading, spacing: 12) {
                HStack {
                    AppSectionHeader("Зарплатные Excel", systemImage: "tablecells")
                    Spacer()
                    if !state.salarySummaryText.isEmpty {
                        AppPill(title: state.salarySummaryText, systemImage: "tablecells", tone: .info)
                    }
                }

                if !state.salaryUnknownEmployees.isEmpty {
                    VStack(alignment: .leading, spacing: 10) {
                        Text("Выберите офис для каждого нового сотрудника")
                            .font(.system(size: 13, weight: .semibold))
                            .foregroundStyle(AppPalette.textSecondary)

                        ForEach(state.salaryUnknownEmployees) { item in
                            HStack(spacing: 12) {
                                VStack(alignment: .leading, spacing: 3) {
                                    Text(item.employee)
                                        .font(.system(size: 13, weight: .semibold))
                                        .foregroundStyle(AppPalette.textPrimary)
                                    Text("\(item.rows) выплат · \(item.amount)")
                                        .font(.system(size: 12, weight: .medium))
                                        .foregroundStyle(AppPalette.textSecondary)
                                }
                                .frame(maxWidth: .infinity, alignment: .leading)

                                Picker("", selection: Binding(
                                    get: { state.salaryOfficeAssignments[item.employee] ?? "" },
                                    set: { state.salaryOfficeAssignments[item.employee] = $0 }
                                )) {
                                    Text("Офис").tag("")
                                    ForEach(state.officeItems, id: \.self) { office in
                                        Text(office).tag(office)
                                    }
                                }
                                .pickerStyle(.menu)
                                .frame(width: 120)
                            }
                            .padding(10)
                            .background(
                                RoundedRectangle(cornerRadius: 6, style: .continuous)
                                    .fill(AppPalette.panelMuted)
                                    .overlay(
                                        RoundedRectangle(cornerRadius: 6, style: .continuous)
                                            .stroke(AppPalette.stroke, lineWidth: 1)
                                    )
                            )
                        }
                    }
                }

                if !state.salaryCreatedFiles.isEmpty {
                    VStack(alignment: .leading, spacing: 10) {
                        Text("Созданные таблицы")
                            .font(.system(size: 13, weight: .semibold))
                            .foregroundStyle(AppPalette.textSecondary)

                        ForEach(state.salaryCreatedFiles) { file in
                            HStack(spacing: 12) {
                                VStack(alignment: .leading, spacing: 3) {
                                    Text(file.name)
                                        .font(.system(size: 13, weight: .semibold))
                                        .foregroundStyle(AppPalette.textPrimary)
                                        .lineLimit(1)
                                        .truncationMode(.middle)
                                    Text("\(file.rows) выплат · \(file.employees) сотрудников · \(file.amount)")
                                        .font(.system(size: 12, weight: .medium))
                                        .foregroundStyle(AppPalette.textSecondary)
                                }
                                Spacer()
                                Button {
                                    state.openSalaryCreatedFile(file)
                                } label: {
                                    Label("Открыть", systemImage: "doc")
                                }
                                .buttonStyle(AppSecondaryButtonStyle())
                            }
                            .padding(10)
                            .background(
                                RoundedRectangle(cornerRadius: 6, style: .continuous)
                                    .fill(AppPalette.panelMuted)
                                    .overlay(
                                        RoundedRectangle(cornerRadius: 6, style: .continuous)
                                            .stroke(AppPalette.stroke, lineWidth: 1)
                                    )
                            )
                        }
                    }
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .appCard()
        }
    }

    @ViewBuilder
    private func manualReviewSection(maxWidth: CGFloat) -> some View {
        if state.runOperation == .sorting && !state.resultArchivePath.isEmpty {
            let isWide = maxWidth >= 620
            let layout = isWide
                ? AnyLayout(HStackLayout(alignment: .top, spacing: 14))
                : AnyLayout(VStackLayout(alignment: .leading, spacing: 14))
            VStack(alignment: .leading, spacing: 12) {
                HStack {
                    AppSectionHeader("Ручная корректировка", systemImage: "hand.raised")
                    Spacer()
                    AppPill(title: "\(state.manualReviewItems.count) файлов", systemImage: "tray.full", tone: .warning)
                }

                    VStack(alignment: .leading, spacing: 10) {
                        Text("Файлы")
                            .font(.system(size: 13, weight: .semibold))
                            .foregroundStyle(AppPalette.textSecondary)

                        ScrollView {
                            LazyVStack(alignment: .leading, spacing: 8) {
                                if state.manualReviewItems.isEmpty {
                                    Text("В ручной папке пока нет файлов.")
                                        .font(.system(size: 13, weight: .medium))
                                        .foregroundStyle(AppPalette.textSecondary)
                                        .frame(maxWidth: .infinity, alignment: .leading)
                                        .padding(12)
                                } else {
                                    ForEach(state.manualReviewItems) { item in
                                        Button {
                                            state.selectedManualReviewItemID = item.id
                                            state.prepareSelectedManualReviewDefaults()
                                        } label: {
                                            Text(item.name)
                                                .font(.system(size: 12.5, weight: .medium))
                                                .foregroundStyle(state.selectedManualReviewItemID == item.id ? AppPalette.textPrimary : AppPalette.textSecondary)
                                                .lineLimit(1)
                                                .truncationMode(.middle)
                                                .frame(maxWidth: .infinity, alignment: .leading)
                                                .padding(.horizontal, 10)
                                                .padding(.vertical, 8)
                                                .background(
                                                    RoundedRectangle(cornerRadius: 6, style: .continuous)
                                                        .fill(state.selectedManualReviewItemID == item.id ? AppPalette.accentMuted : AppPalette.panelMuted)
                                                        .overlay(
                                                            RoundedRectangle(cornerRadius: 6, style: .continuous)
                                                                .stroke(state.selectedManualReviewItemID == item.id ? AppPalette.accent.opacity(0.35) : AppPalette.stroke, lineWidth: 1)
                                                        )
                                                )
                                        }
                                        .buttonStyle(.plain)
                                    }
                                }
                            }
                        }
                        .frame(height: 100)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)

                layout {
                    if let selected = state.selectedManualReviewItem {
                        DocumentReviewPreview(url: selected.url)
                            .id(selected.id)
                            .frame(minWidth: 180, maxWidth: isWide ? 270 : .infinity, minHeight: 420, maxHeight: 520)
                            .accessibilityLabel("Просмотр выбранного документа")
                    }

                    VStack(alignment: .leading, spacing: 12) {
                        if let selected = state.selectedManualReviewItem {
                            VStack(alignment: .leading, spacing: 6) {
                                Text(selected.name)
                                    .font(.system(size: 13, weight: .semibold))
                                    .foregroundStyle(AppPalette.textPrimary)
                                    .lineLimit(1)
                                    .truncationMode(.middle)
                                Text(state.selectedManualReviewReason)
                                    .font(.system(size: 12, weight: .regular))
                                    .foregroundStyle(AppPalette.textSecondary)
                                    .lineLimit(state.selectedManualReviewIsSalaryDuplicate ? 4 : 2)
                            }
                        }

                        Grid(alignment: .leading, horizontalSpacing: 12, verticalSpacing: 10) {
                            GridRow {
                                manualFieldLabel("Тип")
                                manualReviewTypePicker
                            }

                            GridRow {
                                manualFieldLabel("Офис")
                                Picker("", selection: $state.manualReviewOffice) {
                                    Text("Не выбран").tag("")
                                    ForEach(state.officeItems, id: \.self) { office in
                                        Text(office).tag(office)
                                    }
                                }
                                .pickerStyle(.menu)
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .onChange(of: state.manualReviewOffice) { office in
                                    state.syncManualReviewOfficeSelection(office)
                                }
                            }

                            GridRow {
                                manualFieldLabel("ООО / юрлицо")
                                Picker("", selection: $state.manualReviewEntity) {
                                    Text("Не выбрано").tag("")
                                    ForEach(state.manualReviewAvailableEntities, id: \.self) { entity in
                                        Text(entity).tag(entity)
                                    }
                                }
                                .pickerStyle(.menu)
                                .frame(maxWidth: .infinity, alignment: .leading)
                            }

                            GridRow {
                                manualFieldLabel("Категория")
                                Picker("", selection: $state.manualReviewCategory) {
                                    ForEach(state.manualReviewAvailableCategories, id: \.self) { category in
                                        Text(category).tag(category)
                                    }
                                }
                                .pickerStyle(.menu)
                                .frame(maxWidth: .infinity, alignment: .leading)
                            }

                            GridRow {
                                manualFieldLabel("Сотрудник / контрагент")
                                TextField("", text: $state.manualReviewCounterpartyOrSubfolder)
                                    .appField()
                            }
                            GridRow {
                                manualFieldLabel("Дата платежа")
                                TextField("ДД-ММ-ГГГГ", text: $state.manualReviewPaymentDate)
                                    .appField()
                            }
                            GridRow {
                                manualFieldLabel("Сумма платежа")
                                TextField("0,00", text: $state.manualReviewPaymentAmount)
                                    .appField()
                            }
                        }

                        Label("Решение будет сохранено в правилах выбранного офиса", systemImage: "checkmark.shield")
                            .font(.system(size: 12, weight: .semibold))
                            .foregroundStyle(AppPalette.accent)
                            .padding(.vertical, 4)

                        WrappingHStack(horizontalSpacing: 10, verticalSpacing: 10) {
                            Button {
                                state.applyManualReviewSelection()
                            } label: {
                                Label(
                                    state.selectedManualReviewIsSalaryDuplicate ? "Оставить как выплату" : "Применить",
                                    systemImage: "checkmark"
                                )
                            }
                            .buttonStyle(AppPrimaryButtonStyle())
                            .disabled(state.selectedManualReviewItem == nil || state.manualReviewOffice.isEmpty || state.isRunning)

                            Button {
                                state.openSelectedManualReviewFile()
                            } label: {
                                Label("Открыть файл", systemImage: "doc")
                            }
                            .buttonStyle(AppSecondaryButtonStyle())
                            .disabled(state.selectedManualReviewItem == nil)

                            Button {
                                if state.selectedManualReviewIsSalaryDuplicate {
                                    state.excludeSelectedSalaryDuplicate()
                                } else {
                                    state.deleteSelectedManualReviewFile()
                                }
                            } label: {
                                Label(
                                    state.selectedManualReviewIsSalaryDuplicate ? "Это дубль" : "Удалить",
                                    systemImage: state.selectedManualReviewIsSalaryDuplicate ? "archivebox" : "trash"
                                )
                            }
                            .buttonStyle(AppDestructiveButtonStyle())
                            .disabled(state.selectedManualReviewItem == nil || state.isRunning)
                        }
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .appCard()
        }
    }

    private var logSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                AppSectionHeader("Журнал", systemImage: "text.alignleft")
                Spacer()
                AppPill(title: state.isRunning ? "Идет обработка" : "Ожидание", systemImage: state.isRunning ? "bolt.horizontal.fill" : "clock", tone: state.isRunning ? .accent : .neutral)
            }

            ScrollViewReader { proxy in
                ScrollView {
                    VStack(alignment: .leading, spacing: 0) {
                        Text(state.logText)
                            .font(.system(size: 12, weight: .regular, design: .monospaced))
                            .foregroundStyle(AppPalette.textPrimary)
                            .textSelection(.enabled)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(12)
                        Color.clear
                            .frame(height: 1)
                            .id("log-bottom")
                    }
                }
                .frame(height: logViewportHeight)
                .background(
                    RoundedRectangle(cornerRadius: 6, style: .continuous)
                        .fill(AppPalette.panelMuted)
                        .overlay(
                            RoundedRectangle(cornerRadius: 6, style: .continuous)
                                .stroke(AppPalette.stroke, lineWidth: 1)
                        )
                )
                .onChange(of: state.logText) { _ in
                    withAnimation(.easeOut(duration: 0.15)) {
                        proxy.scrollTo("log-bottom", anchor: .bottom)
                    }
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .appCard()
    }

    private var statusSection: some View {
        HStack {
            Text(state.statusText)
                .font(.system(size: 13, weight: .medium))
                .foregroundStyle(AppPalette.textSecondary)
            Spacer()
            if state.manualReviewCount > 0 {
                AppPill(title: "Ручная проверка: \(state.manualReviewCount)", systemImage: "exclamationmark.bubble")
            }
            if state.unresolvedCount > 0 {
                AppPill(title: "Не распределено: \(state.unresolvedCount)", systemImage: "questionmark.folder")
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .appCard()
    }

    @ViewBuilder
    private func parameterRow<Field: View, Action: View>(title: String, @ViewBuilder field: () -> Field, @ViewBuilder action: () -> Action) -> some View {
        GridRow {
            Text(title)
                .font(.system(size: 13, weight: .semibold))
                .foregroundStyle(AppPalette.textSecondary)
                .frame(width: 170, alignment: .leading)
            field()
            action()
        }
    }

    private func manualFieldLabel(_ title: String) -> some View {
        Text(title)
            .font(.system(size: 13, weight: .semibold))
            .foregroundStyle(AppPalette.textSecondary)
            .frame(width: 130, alignment: .leading)
    }
}

private struct WrappingHStack<Content: View>: View {
    let horizontalSpacing: CGFloat
    let verticalSpacing: CGFloat
    @ViewBuilder let content: Content

    var body: some View {
        FlowLayout(horizontalSpacing: horizontalSpacing, verticalSpacing: verticalSpacing) {
            content
        }
    }
}

private struct FlowLayout: Layout {
    let horizontalSpacing: CGFloat
    let verticalSpacing: CGFloat

    init(horizontalSpacing: CGFloat, verticalSpacing: CGFloat) {
        self.horizontalSpacing = horizontalSpacing
        self.verticalSpacing = verticalSpacing
    }

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let rows = arrangeRows(proposal: proposal, subviews: subviews)
        let width = rows.map(\.width).max() ?? 0
        let height = rows.reduce(0) { partial, row in
            partial + row.height
        } + CGFloat(max(rows.count - 1, 0)) * verticalSpacing
        return CGSize(width: width, height: height)
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        let rows = arrangeRows(proposal: proposal, subviews: subviews)
        var y = bounds.minY

        for row in rows {
            var x = bounds.minX
            for element in row.elements {
                let size = element.size
                element.subview.place(
                    at: CGPoint(x: x, y: y),
                    anchor: .topLeading,
                    proposal: ProposedViewSize(width: size.width, height: size.height)
                )
                x += size.width + horizontalSpacing
            }
            y += row.height + verticalSpacing
        }
    }

    private func arrangeRows(proposal: ProposedViewSize, subviews: Subviews) -> [FlowRow] {
        let maxWidth = proposal.width ?? .greatestFiniteMagnitude
        var rows: [FlowRow] = []
        var current = FlowRow()

        for subview in subviews {
            let size = subview.sizeThatFits(.unspecified)
            let nextWidth = current.elements.isEmpty ? size.width : current.width + horizontalSpacing + size.width

            if nextWidth > maxWidth, !current.elements.isEmpty {
                rows.append(current)
                current = FlowRow()
            }

            if !current.elements.isEmpty {
                current.width += horizontalSpacing
            }
            current.elements.append(FlowElement(subview: subview, size: size))
            current.width += size.width
            current.height = max(current.height, size.height)
        }

        if !current.elements.isEmpty {
            rows.append(current)
        }

        return rows
    }
}

private struct FlowRow {
    var elements: [FlowElement] = []
    var width: CGFloat = 0
    var height: CGFloat = 0
}

private struct FlowElement {
    let subview: LayoutSubview
    let size: CGSize
}
