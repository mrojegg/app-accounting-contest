import SwiftUI

struct SettingsRootView: View {
    @ObservedObject var state: AppState

    var body: some View {
        HStack(spacing: 0) {
            settingsSidebar

            Divider()
                .overlay(AppPalette.stroke)

            VStack(spacing: 0) {
                settingsToolbar

                Divider()
                    .overlay(AppPalette.stroke)

                settingsContent
            }
            .background(AppChromeBackground())
        }
        .foregroundStyle(AppPalette.textPrimary)
        .tint(AppPalette.accent)
        .frame(minWidth: 1180, minHeight: 740)
        .alert("Ошибка", isPresented: Binding(
            get: { state.errorMessage != nil },
            set: { if !$0 { state.errorMessage = nil } }
        )) {
            Button("OK") { state.errorMessage = nil }
        } message: {
            Text(state.errorMessage ?? "")
        }
    }

    private var settingsToolbar: some View {
        HStack(spacing: 12) {
            ZStack {
                RoundedRectangle(cornerRadius: 7, style: .continuous)
                    .fill(AppPalette.accentMuted)
                Image(systemName: state.selectedSettingsSection == .offices ? "building.2.fill" : "book.closed.fill")
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundStyle(AppPalette.accent)
            }
            .frame(width: 36, height: 36)

            VStack(alignment: .leading, spacing: 2) {
                Text(state.selectedSettingsSection == .offices ? "Управление офисами" : "Гайд по приложению")
                    .font(.system(size: 16, weight: .semibold))
                    .foregroundStyle(AppPalette.textPrimary)
                Text(state.selectedSettingsSection == .offices ? "Выбран офис \(state.selectedOffice)" : "Сортировка, обработка и результаты")
                    .font(.system(size: 11, weight: .medium))
                    .foregroundStyle(AppPalette.textSecondary)
            }

            Spacer()

            if state.selectedSettingsSection == .offices {
                Button {
                    state.closeSettingsWithoutSaving()
                } label: {
                    Image(systemName: "xmark")
                }
                .buttonStyle(SettingsIconButtonStyle())
                .help("Закрыть без сохранения")

                Button {
                    state.saveSettingsAndClose()
                } label: {
                    Label("Сохранить и закрыть", systemImage: "checkmark")
                }
                .buttonStyle(SettingsToolbarButtonStyle(isPrimary: true))
            } else {
                Button {
                    state.closeSettingsWithoutSaving()
                } label: {
                    Label("Закрыть", systemImage: "xmark")
                }
                .buttonStyle(SettingsToolbarButtonStyle())
            }
        }
        .padding(.horizontal, 18)
        .padding(.vertical, 12)
        .background(AppPalette.panel)
    }

    private var settingsSidebar: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(spacing: 10) {
                ZStack {
                    RoundedRectangle(cornerRadius: 7, style: .continuous)
                        .fill(Color.white.opacity(0.12))
                    Image(systemName: "square.grid.2x2")
                        .font(.system(size: 14, weight: .semibold))
                        .foregroundStyle(AppPalette.sidebarText)
                }
                .frame(width: 34, height: 34)

                VStack(alignment: .leading, spacing: 2) {
                    Text("Рабочий центр")
                        .font(.system(size: 16, weight: .semibold))
                        .foregroundStyle(AppPalette.sidebarText)
                    Text("Офисы и справка")
                        .font(.system(size: 10, weight: .medium))
                        .foregroundStyle(AppPalette.sidebarTextSecondary)
                }
            }
            .padding(.horizontal, 12)
            .padding(.bottom, 22)

            Text("РАЗДЕЛЫ")
                .font(.system(size: 11, weight: .semibold))
                .foregroundStyle(AppPalette.sidebarTextSecondary)
                .padding(.horizontal, 12)
                .padding(.bottom, 8)

            VStack(spacing: 5) {
                ForEach(SettingsSection.allCases) { section in
                    settingsSidebarButton(section)
                }
            }

            Spacer()
        }
        .padding(12)
        .frame(width: 236)
        .frame(maxHeight: .infinity, alignment: .top)
        .background(AppPalette.sidebar)
    }

    private func settingsSidebarButton(_ section: SettingsSection) -> some View {
        let isSelected = state.selectedSettingsSection == section
        return Button {
            state.selectedSettingsSection = section
            switch section {
            case .offices:
                state.loadOfficeRules()
            case .admin:
                break
            }
        } label: {
            HStack(spacing: 11) {
                ZStack {
                    RoundedRectangle(cornerRadius: 6, style: .continuous)
                        .fill(isSelected ? Color.white.opacity(0.10) : Color.clear)
                    Image(systemName: section.icon)
                        .font(.system(size: 14, weight: .semibold))
                }
                .frame(width: 30, height: 30)

                VStack(alignment: .leading, spacing: 2) {
                    Text(section.rawValue)
                        .font(.system(size: 13, weight: .semibold))
                    Text(settingsSectionSubtitle(section))
                        .font(.system(size: 10, weight: .medium))
                        .foregroundStyle(AppPalette.sidebarTextSecondary)
                        .lineLimit(1)
                }
                Spacer(minLength: 0)
                if isSelected {
                    Image(systemName: "chevron.right")
                        .font(.system(size: 10, weight: .bold))
                }
            }
            .foregroundStyle(isSelected ? AppPalette.sidebarText : AppPalette.sidebarTextSecondary)
            .padding(.horizontal, 10)
            .frame(height: 54)
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

    private func settingsSectionSubtitle(_ section: SettingsSection) -> String {
        switch section {
        case .offices:
            return "Сотрудники и контрагенты"
        case .admin:
            return "Возможности и порядок работы"
        }
    }

    @ViewBuilder
    private var settingsContent: some View {
        switch state.selectedSettingsSection {
        case .offices:
            OfficeSettingsView(state: state)
        case .admin:
            AdminSettingsView(state: state)
        }
    }
}

private enum OfficeDetailTab: String, CaseIterable, Identifiable {
    case overview = "Обзор"
    case employees = "Сотрудники"
    case contractors = "Контрагенты"

    var id: String { rawValue }

    var icon: String {
        switch self {
        case .overview: return "square.grid.2x2"
        case .employees: return "person.2"
        case .contractors: return "building.2"
        }
    }
}

private struct OfficeSettingsView: View {
    @ObservedObject var state: AppState
    @State private var selectedTab: OfficeDetailTab = .overview
    @State private var employeeSearch = ""
    @State private var selectedContractorCategory = ""
    @State private var hoveredEmployeeIndex: Int?
    @State private var isAddingOffice = false

    var body: some View {
        VStack(spacing: 0) {
            officeSwitcher

            Divider()
                .overlay(AppPalette.stroke)

            officeDetailHeader

            officeTabBar

            Divider()
                .overlay(AppPalette.stroke)

            officeDetailContent
        }
        .background(AppChromeBackground())
    }

    private var officeSwitcher: some View {
        VStack(alignment: .leading, spacing: 9) {
            HStack(spacing: 8) {
                Label("Офисы", systemImage: "building.2")
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundStyle(AppPalette.textPrimary)

                Text("\(state.officeItems.count)")
                    .font(.system(size: 10, weight: .bold))
                    .foregroundStyle(AppPalette.accent)
                    .padding(.horizontal, 7)
                    .padding(.vertical, 3)
                    .background(Capsule(style: .continuous).fill(AppPalette.accentMuted))

                Spacer()

                Button {
                    isAddingOffice = true
                } label: {
                    Label("Новый офис", systemImage: "plus")
                }
                .buttonStyle(SettingsCompactButtonStyle())
                .popover(isPresented: $isAddingOffice, arrowEdge: .bottom) {
                    addOfficePopover
                }
            }

            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 8) {
                    ForEach(state.officeItems, id: \.self) { office in
                        Button {
                            state.selectedOffice = office
                            state.loadOfficeRules()
                        } label: {
                            officeSwitcherTile(office)
                        }
                        .buttonStyle(.plain)
                    }

                }
                .padding(.horizontal, 1)
            }
        }
        .padding(.horizontal, 18)
        .padding(.vertical, 12)
        .background(AppPalette.panelRaised)
    }

    private func officeSwitcherTile(_ office: String) -> some View {
        let isSelected = state.selectedOffice == office
        return HStack(spacing: 9) {
            ZStack {
                RoundedRectangle(cornerRadius: 6, style: .continuous)
                    .fill(isSelected ? Color.white.opacity(0.14) : AppPalette.accentMuted)
                Image(systemName: "building.2.fill")
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundStyle(isSelected ? Color.white : AppPalette.accent)
            }
            .frame(width: 30, height: 30)

            VStack(alignment: .leading, spacing: 1) {
                Text("ОФИС")
                    .font(.system(size: 8, weight: .bold))
                    .foregroundStyle(isSelected ? Color.white.opacity(0.70) : AppPalette.textSecondary)
                Text(office)
                    .font(.system(size: 13, weight: .bold))
                    .foregroundStyle(isSelected ? Color.white : AppPalette.textPrimary)
                    .minimumScaleFactor(0.75)
                    .lineLimit(1)
            }
        }
        .padding(.horizontal, 10)
        .frame(width: 104, height: 52, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .fill(isSelected ? AppPalette.accent : AppPalette.panel)
                .overlay(
                    RoundedRectangle(cornerRadius: 8, style: .continuous)
                        .stroke(isSelected ? AppPalette.accent : AppPalette.stroke, lineWidth: 1)
                )
        )
        .shadow(color: isSelected ? AppPalette.accent.opacity(0.18) : AppPalette.shadow, radius: 3, x: 0, y: 1)
    }

    private var addOfficePopover: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(spacing: 10) {
                ZStack {
                    RoundedRectangle(cornerRadius: 7, style: .continuous)
                        .fill(AppPalette.accentMuted)
                    Image(systemName: "building.2.badge.plus")
                        .font(.system(size: 14, weight: .semibold))
                        .foregroundStyle(AppPalette.accent)
                }
                .frame(width: 34, height: 34)

                VStack(alignment: .leading, spacing: 2) {
                    Text("Новый офис")
                        .font(.system(size: 14, weight: .semibold))
                        .foregroundStyle(AppPalette.textPrimary)
                    Text("Добавление в список офисов")
                        .font(.system(size: 10, weight: .medium))
                        .foregroundStyle(AppPalette.textSecondary)
                }
            }

            TextField("Номер офиса", text: $state.newOfficeInput)
                .settingsCompactField()
                .onSubmit(createOfficeFromPopover)

            HStack {
                Spacer()
                Button("Отмена") {
                    isAddingOffice = false
                }
                .buttonStyle(SettingsCompactButtonStyle())

                Button {
                    createOfficeFromPopover()
                } label: {
                    Label("Создать", systemImage: "plus")
                }
                .buttonStyle(SettingsCompactButtonStyle(isPrimary: true))
                .disabled(state.newOfficeInput.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
            }
        }
        .padding(16)
        .frame(width: 290)
        .background(AppPalette.panel)
    }

    private func createOfficeFromPopover() {
        state.addOffice()
        isAddingOffice = false
    }

    private var officeDetailHeader: some View {
        HStack(spacing: 14) {
            ZStack {
                RoundedRectangle(cornerRadius: 8, style: .continuous)
                    .fill(AppPalette.accent)
                Text(state.selectedOffice)
                    .font(.system(size: 14, weight: .bold))
                    .foregroundStyle(Color.white)
                    .minimumScaleFactor(0.65)
                    .lineLimit(1)
                    .padding(5)
            }
            .frame(width: 46, height: 46)

            VStack(alignment: .leading, spacing: 3) {
                Text("Офис \(state.selectedOffice)")
                    .font(.system(size: 19, weight: .semibold))
                    .foregroundStyle(AppPalette.textPrimary)
                Text(state.officeEntityInput.isEmpty ? "Юрлицо не указано" : state.officeEntityInput)
                    .font(.system(size: 11, weight: .medium))
                    .foregroundStyle(AppPalette.textSecondary)
                    .lineLimit(1)
            }

            Spacer()

            Button {
                state.loadOfficeRules()
            } label: {
                Image(systemName: "arrow.clockwise")
            }
            .buttonStyle(SettingsIconButtonStyle())
            .help("Обновить")

            Menu {
                Button(role: .destructive) {
                    state.deleteSelectedOffice()
                } label: {
                    Label("Удалить офис", systemImage: "trash")
                }
                .disabled(state.officeItems.count <= 1)
            } label: {
                Image(systemName: "ellipsis")
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundStyle(AppPalette.textPrimary)
                    .frame(width: 32, height: 32)
                    .background(
                        RoundedRectangle(cornerRadius: 8, style: .continuous)
                            .fill(AppPalette.panelRaised)
                            .overlay(
                                RoundedRectangle(cornerRadius: 8, style: .continuous)
                                    .stroke(AppPalette.stroke, lineWidth: 1)
                            )
                    )
            }
            .menuStyle(.borderlessButton)
            .menuIndicator(.hidden)
            .fixedSize()

            Button {
                state.saveOfficeRules()
            } label: {
                Label("Сохранить", systemImage: "checkmark")
            }
            .buttonStyle(SettingsCompactButtonStyle(isPrimary: true))
        }
        .padding(.horizontal, 18)
        .padding(.vertical, 14)
        .background(AppPalette.panel)
    }

    private var officeTabBar: some View {
        HStack(spacing: 2) {
            ForEach(OfficeDetailTab.allCases) { tab in
                let isSelected = selectedTab == tab
                Button {
                    selectedTab = tab
                } label: {
                    HStack(spacing: 7) {
                        Image(systemName: tab.icon)
                            .font(.system(size: 12, weight: .semibold))
                        Text(tab.rawValue)
                            .font(.system(size: 12, weight: .semibold))
                        if tab == .employees {
                            tabCount(state.officeEmployees.count, selected: isSelected)
                        } else if tab == .contractors {
                            tabCount(totalContractorCount, selected: isSelected)
                        }
                    }
                    .foregroundStyle(isSelected ? AppPalette.accent : AppPalette.textSecondary)
                    .padding(.horizontal, 14)
                    .frame(height: 42)
                    .background(isSelected ? AppPalette.accentMuted.opacity(0.72) : Color.clear)
                    .overlay(alignment: .bottom) {
                        if isSelected {
                            Rectangle()
                                .fill(AppPalette.accent)
                                .frame(height: 2)
                        }
                    }
                }
                .buttonStyle(.plain)
            }
            Spacer()
        }
        .padding(.horizontal, 18)
        .background(AppPalette.panel)
    }

    private func tabCount(_ value: Int, selected: Bool) -> some View {
        Text("\(value)")
            .font(.system(size: 9, weight: .bold))
            .foregroundStyle(selected ? AppPalette.accent : AppPalette.textSecondary)
            .padding(.horizontal, 6)
            .padding(.vertical, 2)
            .background(Capsule(style: .continuous).fill(selected ? AppPalette.panel : AppPalette.panelMuted))
    }

    @ViewBuilder
    private var officeDetailContent: some View {
        switch selectedTab {
        case .overview:
            officeOverview
        case .employees:
            employeesPanel
        case .contractors:
            contractorsPanel
        }
    }

    private var officeOverview: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                VStack(alignment: .leading, spacing: 14) {
                    settingsPanelTitle("Профиль офиса", icon: "building.2")

                    HStack(spacing: 18) {
                        VStack(alignment: .leading, spacing: 6) {
                            Text("НОМЕР")
                                .font(.system(size: 10, weight: .bold))
                                .foregroundStyle(AppPalette.textSecondary)
                            Text(state.selectedOffice)
                                .font(.system(size: 26, weight: .semibold))
                                .foregroundStyle(AppPalette.textPrimary)
                        }
                        .frame(width: 112, alignment: .leading)

                        Rectangle()
                            .fill(AppPalette.stroke)
                            .frame(width: 1, height: 54)

                        VStack(alignment: .leading, spacing: 6) {
                            Text("ЮРИДИЧЕСКОЕ ЛИЦО")
                                .font(.system(size: 10, weight: .bold))
                                .foregroundStyle(AppPalette.textSecondary)
                            TextField("ООО ВАША КОМПАНИЯ", text: $state.officeEntityInput)
                                .settingsCompactField()
                        }
                        .frame(maxWidth: .infinity)
                    }
                }
                .premiumSettingsPanel()

                HStack(spacing: 0) {
                    summaryMetric(value: state.officeEmployees.count, title: "Сотрудников", icon: "person.2")
                    metricDivider
                    summaryMetric(value: state.officeAllowedCategories.count, title: "Категорий", icon: "square.grid.2x2")
                    metricDivider
                    summaryMetric(value: totalContractorCount, title: "Контрагентов", icon: "building.2")
                }
                .premiumSettingsPanel()

                VStack(alignment: .leading, spacing: 14) {
                    settingsPanelTitle("Категории документов", icon: "tray.full")

                    LazyVGrid(columns: [GridItem(.adaptive(minimum: 190), spacing: 10)], spacing: 10) {
                        ForEach(availableOfficeCategories(), id: \.self) { category in
                            let enabled = state.officeAllowedCategories.contains(category)
                            Toggle(isOn: categoryBinding(category)) {
                                Label(category, systemImage: categoryIcon(category))
                                    .font(.system(size: 12, weight: .semibold))
                                    .foregroundStyle(enabled ? AppPalette.accent : AppPalette.textPrimary)
                            }
                            .toggleStyle(.checkbox)
                            .padding(.horizontal, 11)
                            .frame(height: 42)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .background(
                                RoundedRectangle(cornerRadius: 7, style: .continuous)
                                    .fill(enabled ? AppPalette.accentMuted : AppPalette.panelRaised)
                                    .overlay(
                                        RoundedRectangle(cornerRadius: 7, style: .continuous)
                                            .stroke(enabled ? AppPalette.accent.opacity(0.28) : AppPalette.stroke, lineWidth: 1)
                                    )
                            )
                        }
                    }
                }
                .premiumSettingsPanel()
            }
            .padding(18)
        }
    }

    private var employeesPanel: some View {
        VStack(spacing: 0) {
            HStack(spacing: 12) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Сотрудники")
                        .font(.system(size: 17, weight: .semibold))
                        .foregroundStyle(AppPalette.textPrimary)
                    Text("\(state.officeEmployees.count) в офисе")
                        .font(.system(size: 11, weight: .medium))
                        .foregroundStyle(AppPalette.textSecondary)
                }

                Spacer()

                HStack(spacing: 7) {
                    Image(systemName: "magnifyingglass")
                        .foregroundStyle(AppPalette.textSecondary)
                    TextField("Поиск по ФИО", text: $employeeSearch)
                        .textFieldStyle(.plain)
                        .font(.system(size: 12, weight: .medium))
                }
                .padding(.horizontal, 10)
                .frame(width: 220, height: 34)
                .background(
                    RoundedRectangle(cornerRadius: 7, style: .continuous)
                        .fill(AppPalette.panel)
                        .overlay(
                            RoundedRectangle(cornerRadius: 7, style: .continuous)
                                .stroke(AppPalette.stroke, lineWidth: 1)
                        )
                )

                Button {
                    state.officeEmployees.append("")
                    employeeSearch = ""
                } label: {
                    Label("Добавить", systemImage: "plus")
                }
                .buttonStyle(SettingsCompactButtonStyle(isPrimary: true))
            }
            .padding(18)

            HStack {
                Text("СОТРУДНИК")
                Spacer()
                Text("ДЕЙСТВИЯ")
            }
            .font(.system(size: 10, weight: .bold))
            .foregroundStyle(AppPalette.textSecondary)
            .padding(.horizontal, 18)
            .frame(height: 32)
            .background(AppPalette.panelMuted.opacity(0.62))

            ScrollView {
                LazyVStack(spacing: 0) {
                    ForEach(filteredEmployeeIndices, id: \.self) { index in
                        employeeRow(index)
                        Divider()
                            .overlay(AppPalette.stroke.opacity(0.65))
                            .padding(.leading, 62)
                    }
                }
                .background(AppPalette.panel)
            }
        }
        .background(AppPalette.panel)
    }

    private var contractorsPanel: some View {
        VStack(spacing: 0) {
            HStack(spacing: 12) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Контрагенты")
                        .font(.system(size: 17, weight: .semibold))
                        .foregroundStyle(AppPalette.textPrimary)
                    Text("\(totalContractorCount) правил в офисе")
                        .font(.system(size: 11, weight: .medium))
                        .foregroundStyle(AppPalette.textSecondary)
                }

                Spacer()

                Picker("Категория", selection: contractorCategoryBinding) {
                    ForEach(availableContractorCategories(), id: \.self) { category in
                        Text(category).tag(category)
                    }
                }
                .pickerStyle(.menu)
                .frame(width: 190)

                Button {
                    let category = activeContractorCategory
                    guard !category.isEmpty else { return }
                    state.officeContractorRules[category, default: []].append(
                        ContractorRuleForm(name: "", createFolder: false, aliases: [""])
                    )
                } label: {
                    Label("Добавить", systemImage: "plus")
                }
                .buttonStyle(SettingsCompactButtonStyle(isPrimary: true))
            }
            .padding(18)

            Divider()
                .overlay(AppPalette.stroke)

            ScrollView {
                LazyVStack(alignment: .leading, spacing: 12) {
                    ForEach(Array(contractorRules(activeContractorCategory).enumerated()), id: \.element.id) { index, _ in
                        contractorRuleEditor(category: activeContractorCategory, index: index)
                    }

                    if contractorRules(activeContractorCategory).isEmpty {
                        VStack(spacing: 10) {
                            Image(systemName: "building.2")
                                .font(.system(size: 25, weight: .medium))
                                .foregroundStyle(AppPalette.textSecondary)
                            Text("В категории нет контрагентов")
                                .font(.system(size: 13, weight: .semibold))
                                .foregroundStyle(AppPalette.textSecondary)
                        }
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 80)
                    }
                }
                .padding(18)
            }
        }
        .background(AppPalette.panelRaised)
    }

    private func settingsPanelTitle(_ title: String, icon: String) -> some View {
        Label(title, systemImage: icon)
            .font(.system(size: 14, weight: .semibold))
            .foregroundStyle(AppPalette.textPrimary)
    }

    private func summaryMetric(value: Int, title: String, icon: String) -> some View {
        HStack(spacing: 11) {
            Image(systemName: icon)
                .font(.system(size: 15, weight: .semibold))
                .foregroundStyle(AppPalette.accent)
                .frame(width: 30, height: 30)
                .background(RoundedRectangle(cornerRadius: 7, style: .continuous).fill(AppPalette.accentMuted))
            VStack(alignment: .leading, spacing: 1) {
                Text("\(value)")
                    .font(.system(size: 18, weight: .semibold))
                    .foregroundStyle(AppPalette.textPrimary)
                Text(title)
                    .font(.system(size: 10, weight: .medium))
                    .foregroundStyle(AppPalette.textSecondary)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private var metricDivider: some View {
        Rectangle()
            .fill(AppPalette.stroke)
            .frame(width: 1, height: 38)
    }

    private var filteredEmployeeIndices: [Int] {
        let query = employeeSearch.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !query.isEmpty else { return Array(state.officeEmployees.indices) }
        return state.officeEmployees.indices.filter {
            state.officeEmployees[$0].localizedCaseInsensitiveContains(query)
        }
    }

    private func employeeRow(_ index: Int) -> some View {
        HStack(spacing: 12) {
            ZStack {
                Circle()
                    .fill(index.isMultiple(of: 2) ? AppPalette.accentMuted : AppPalette.infoMuted)
                Text(employeeInitials(state.officeEmployees[index]))
                    .font(.system(size: 10, weight: .bold))
                    .foregroundStyle(index.isMultiple(of: 2) ? AppPalette.accent : AppPalette.info)
            }
            .frame(width: 32, height: 32)

            TextField("ФИО сотрудника", text: employeeBinding(index))
                .textFieldStyle(.plain)
                .font(.system(size: 13, weight: .medium))
                .foregroundStyle(AppPalette.textPrimary)

            Spacer(minLength: 8)

            Button(role: .destructive) {
                state.officeEmployees.remove(at: index)
            } label: {
                Image(systemName: "trash")
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundStyle(AppPalette.destructive)
                    .frame(width: 28, height: 28)
                    .background(RoundedRectangle(cornerRadius: 6, style: .continuous).fill(AppPalette.destructiveMuted))
            }
            .buttonStyle(.plain)
            .help("Удалить сотрудника")
            .opacity(hoveredEmployeeIndex == index ? 1 : 0)
        }
        .padding(.horizontal, 18)
        .frame(height: 48)
        .contentShape(Rectangle())
        .background(hoveredEmployeeIndex == index ? AppPalette.panelMuted.opacity(0.46) : Color.clear)
        .onHover { hovering in
            hoveredEmployeeIndex = hovering ? index : nil
        }
    }

    private func employeeInitials(_ name: String) -> String {
        let parts = name.split(separator: " ").prefix(2)
        let initials = parts.compactMap(\.first).map(String.init).joined()
        return initials.isEmpty ? "-" : initials.uppercased()
    }

    private var totalContractorCount: Int {
        state.officeContractorRules.values.reduce(0) { $0 + $1.count }
    }

    private var activeContractorCategory: String {
        let categories = availableContractorCategories()
        return categories.contains(selectedContractorCategory) ? selectedContractorCategory : (categories.first ?? "")
    }

    private var contractorCategoryBinding: Binding<String> {
        Binding(
            get: { activeContractorCategory },
            set: { selectedContractorCategory = $0 }
        )
    }

    private func categoryIcon(_ category: String) -> String {
        switch category.lowercased() {
        case let value where value.contains("зарплат"): return "person.2"
        case let value where value.contains("аренд"): return "key"
        case let value where value.contains("интернет"): return "wifi"
        case let value where value.contains("коммун"): return "bolt"
        case let value where value.contains("налог") || value.contains("взнос"): return "building.columns"
        case let value where value.contains("комисс"): return "percent"
        default: return "folder"
        }
    }

    private func categoryBinding(_ category: String) -> Binding<Bool> {
        Binding(
            get: { state.officeAllowedCategories.contains(category) },
            set: { isEnabled in
                if isEnabled {
                    if !state.officeAllowedCategories.contains(category) {
                        state.officeAllowedCategories.append(category)
                    }
                } else {
                    if state.officeAllowedCategories.count > 1 {
                        state.officeAllowedCategories.removeAll { $0 == category }
                    }
                }
            }
        )
    }

    private func contractorRules(_ category: String) -> [ContractorRuleForm] {
        state.officeContractorRules[category, default: []]
    }

    @ViewBuilder
    private func contractorRuleEditor(category: String, index: Int) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 10) {
                ZStack {
                    RoundedRectangle(cornerRadius: 7, style: .continuous)
                        .fill(AppPalette.accentMuted)
                    Image(systemName: "building.2")
                        .font(.system(size: 13, weight: .semibold))
                        .foregroundStyle(AppPalette.accent)
                }
                .frame(width: 34, height: 34)

                TextField("Контрагент", text: contractorNameBinding(category, index: index))
                    .settingsCompactField()

                Toggle("Отдельная папка", isOn: contractorCreateFolderBinding(category, index: index))
                    .toggleStyle(.switch)
                    .font(.system(size: 12, weight: .medium))
                    .foregroundStyle(AppPalette.textPrimary)

                Menu {
                    Button(role: .destructive) {
                        state.officeContractorRules[category, default: []].remove(at: index)
                    } label: {
                        Label("Удалить контрагента", systemImage: "trash")
                    }
                } label: {
                    Image(systemName: "ellipsis")
                        .font(.system(size: 13, weight: .semibold))
                        .foregroundStyle(AppPalette.textSecondary)
                        .frame(width: 30, height: 30)
                        .background(
                            RoundedRectangle(cornerRadius: 7, style: .continuous)
                                .fill(AppPalette.panelRaised)
                                .overlay(
                                    RoundedRectangle(cornerRadius: 7, style: .continuous)
                                        .stroke(AppPalette.stroke, lineWidth: 1)
                                )
                        )
                }
                .menuStyle(.borderlessButton)
                .menuIndicator(.hidden)
                .fixedSize()
            }

            Divider()
                .overlay(AppPalette.stroke)

            VStack(alignment: .leading, spacing: 6) {
                HStack {
                    Text("Написания в документах")
                        .font(.system(size: 11, weight: .semibold))
                        .foregroundStyle(AppPalette.textSecondary)
                    Spacer()
                    Button {
                        addContractorAlias(category: category, index: index)
                    } label: {
                        Label("Добавить", systemImage: "plus")
                    }
                    .buttonStyle(SettingsCompactButtonStyle())
                }

                ForEach(Array(contractorAliases(category, index: index).enumerated()), id: \.offset) { aliasIndex, _ in
                    EditableSettingsRow(
                        placeholder: "Написание в документе",
                        text: contractorAliasBinding(category, index: index, aliasIndex: aliasIndex),
                        deleteHelp: "Удалить алиас"
                    ) {
                        removeContractorAlias(category: category, index: index, aliasIndex: aliasIndex)
                    }
                }
            }
        }
        .padding(14)
        .background(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .fill(AppPalette.panel)
                .overlay(
                    RoundedRectangle(cornerRadius: 8, style: .continuous)
                        .stroke(AppPalette.stroke, lineWidth: 1)
                )
        )
        .shadow(color: AppPalette.shadow, radius: 3, x: 0, y: 1)
    }

    private func contractorNameBinding(_ category: String, index: Int) -> Binding<String> {
        Binding(
            get: {
                let values = state.officeContractorRules[category, default: []]
                guard values.indices.contains(index) else { return "" }
                return values[index].name
            },
            set: { newValue in
                var values = state.officeContractorRules[category, default: []]
                guard values.indices.contains(index) else { return }
                values[index].name = newValue
                state.officeContractorRules[category] = values
            }
        )
    }

    private func contractorCreateFolderBinding(_ category: String, index: Int) -> Binding<Bool> {
        Binding(
            get: {
                let values = state.officeContractorRules[category, default: []]
                guard values.indices.contains(index) else { return false }
                return values[index].createFolder
            },
            set: { newValue in
                var values = state.officeContractorRules[category, default: []]
                guard values.indices.contains(index) else { return }
                values[index].createFolder = newValue
                state.officeContractorRules[category] = values
            }
        )
    }

    private func contractorAliases(_ category: String, index: Int) -> [String] {
        let values = state.officeContractorRules[category, default: []]
        guard values.indices.contains(index) else { return [] }
        return values[index].aliases
    }

    private func addContractorAlias(category: String, index: Int) {
        var values = state.officeContractorRules[category, default: []]
        guard values.indices.contains(index) else { return }
        values[index].aliases.append("")
        state.officeContractorRules[category] = values
    }

    private func removeContractorAlias(category: String, index: Int, aliasIndex: Int) {
        var values = state.officeContractorRules[category, default: []]
        guard values.indices.contains(index), values[index].aliases.indices.contains(aliasIndex) else { return }
        values[index].aliases.remove(at: aliasIndex)
        state.officeContractorRules[category] = values
    }

    private func contractorAliasBinding(_ category: String, index: Int, aliasIndex: Int) -> Binding<String> {
        Binding(
            get: {
                let values = state.officeContractorRules[category, default: []]
                guard values.indices.contains(index), values[index].aliases.indices.contains(aliasIndex) else { return "" }
                return values[index].aliases[aliasIndex]
            },
            set: { newValue in
                var values = state.officeContractorRules[category, default: []]
                guard values.indices.contains(index), values[index].aliases.indices.contains(aliasIndex) else { return }
                values[index].aliases[aliasIndex] = newValue
                state.officeContractorRules[category] = values
            }
        )
    }

    private func employeeBinding(_ index: Int) -> Binding<String> {
        Binding(
            get: { state.officeEmployees.indices.contains(index) ? state.officeEmployees[index] : "" },
            set: { newValue in
                guard state.officeEmployees.indices.contains(index) else { return }
                state.officeEmployees[index] = newValue
            }
        )
    }

    private func availableOfficeCategories() -> [String] {
        let base = state.generalArchiveFolders
            .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }
        let merged = (base.isEmpty ? RulesEditing.standardCategories : base) + state.officeAllowedCategories
        return uniqueOrdered(merged)
    }

    private func availableContractorCategories() -> [String] {
        uniqueOrdered(availableOfficeCategories().filter { $0 != "Зарплата" })
    }

    private func uniqueOrdered(_ values: [String]) -> [String] {
        var seen: Set<String> = []
        return values.filter { seen.insert($0).inserted }
    }
}

private struct OfficeSidebarRow: View {
    let office: String
    let isSelected: Bool

    var body: some View {
        Label {
            Text("Офис \(office)")
                .font(.system(size: 13, weight: .medium))
                .lineLimit(1)
        } icon: {
            Image(systemName: isSelected ? "building.2.fill" : "building.2")
                .font(.system(size: 13, weight: .semibold))
                .frame(width: 18)
        }
        .foregroundStyle(isSelected ? AppPalette.accent : AppPalette.textSecondary)
        .padding(.horizontal, 8)
        .padding(.vertical, 6)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: 6, style: .continuous)
                .fill(isSelected ? AppPalette.accentMuted : Color.clear)
                .overlay(
                    RoundedRectangle(cornerRadius: 6, style: .continuous)
                        .stroke(isSelected ? AppPalette.accent.opacity(0.25) : Color.clear, lineWidth: 1)
                )
        )
    }
}

private struct EditableSettingsRow: View {
    let placeholder: String
    let text: Binding<String>
    let deleteHelp: String
    let onDelete: () -> Void
    @State private var isHovering = false

    var body: some View {
        HStack(spacing: 6) {
            TextField(placeholder, text: text)
                .settingsCompactField()
            Button(role: .destructive, action: onDelete) {
                Image(systemName: "xmark")
                    .font(.system(size: 10, weight: .bold))
                    .foregroundStyle(isHovering ? AppPalette.destructive : AppPalette.textSecondary)
                    .frame(width: 27, height: 27)
                    .background(
                        RoundedRectangle(cornerRadius: 6, style: .continuous)
                            .fill(isHovering ? AppPalette.destructiveMuted : AppPalette.panelRaised)
                            .overlay(
                                RoundedRectangle(cornerRadius: 6, style: .continuous)
                                    .stroke(isHovering ? AppPalette.destructive.opacity(0.24) : AppPalette.stroke, lineWidth: 1)
                            )
                    )
            }
            .buttonStyle(.plain)
            .help(deleteHelp)
        }
        .onHover { isHovering = $0 }
    }
}

private struct RuleBuilderCard: View {
    let title: String
    let systemImage: String
    @Binding var isOn: Bool
    let writeAt: String
    let ruleText: String
    let result: String

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Toggle(isOn: $isOn) {
                Label(title, systemImage: systemImage)
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundStyle(AppPalette.textPrimary)
            }
            .toggleStyle(.switch)

            ruleDetail("Что заполнить", writeAt)
            ruleDetail("Что сохранится", ruleText)
            ruleDetail("Как сработает", result)
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .fill(AppPalette.panel)
                .overlay(
                    RoundedRectangle(cornerRadius: 8, style: .continuous)
                        .stroke(AppPalette.stroke, lineWidth: 1)
                )
        )
    }

    private func ruleDetail(_ title: String, _ value: String) -> some View {
        HStack(alignment: .top, spacing: 10) {
            Text(title)
                .font(.system(size: 12, weight: .semibold))
                .foregroundStyle(AppPalette.textSecondary)
                .frame(width: 112, alignment: .leading)
            Text(value)
                .font(.system(size: 13, weight: .medium))
                .foregroundStyle(AppPalette.textPrimary)
                .textSelection(.enabled)
                .frame(maxWidth: .infinity, alignment: .leading)
        }
    }
}

private struct SettingsToolbarButtonStyle: ButtonStyle {
    @Environment(\.isEnabled) private var isEnabled
    var isPrimary = false

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: 13, weight: .semibold))
            .foregroundStyle(isPrimary ? Color.white : AppPalette.textPrimary)
            .labelStyle(.titleAndIcon)
            .padding(.horizontal, 12)
            .padding(.vertical, 7)
            .background(
                RoundedRectangle(cornerRadius: 8, style: .continuous)
                    .fill(isPrimary ? (configuration.isPressed ? AppPalette.accentPressed : AppPalette.accent) : (configuration.isPressed ? AppPalette.panelMuted : AppPalette.panelRaised))
                    .overlay(
                        RoundedRectangle(cornerRadius: 8, style: .continuous)
                            .stroke(isPrimary ? Color.clear : AppPalette.stroke, lineWidth: 1)
                    )
            )
            .scaleEffect(configuration.isPressed ? 0.985 : 1)
            .opacity(isEnabled ? 1 : 0.42)
    }
}

private struct SettingsCompactButtonStyle: ButtonStyle {
    @Environment(\.isEnabled) private var isEnabled
    var isPrimary = false
    var isDestructive = false

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: 13, weight: .semibold))
            .foregroundStyle(foreground)
            .labelStyle(.titleAndIcon)
            .padding(.horizontal, 11)
            .padding(.vertical, 7)
            .background(
                RoundedRectangle(cornerRadius: 8, style: .continuous)
                    .fill(background(isPressed: configuration.isPressed))
                    .overlay(
                        RoundedRectangle(cornerRadius: 8, style: .continuous)
                            .stroke(border, lineWidth: 1)
                    )
            )
            .scaleEffect(configuration.isPressed ? 0.985 : 1)
            .opacity(isEnabled ? 1 : 0.42)
    }

    private var foreground: Color {
        if isPrimary { return Color.white }
        if isDestructive { return AppPalette.destructive }
        return AppPalette.textPrimary
    }

    private var border: Color {
        if isPrimary { return Color.clear }
        return isDestructive ? AppPalette.destructive.opacity(0.25) : AppPalette.stroke
    }

    private func background(isPressed: Bool) -> Color {
        if isPrimary { return isPressed ? AppPalette.accentPressed : AppPalette.accent }
        if isDestructive { return AppPalette.destructiveMuted.opacity(isPressed ? 0.70 : 1) }
        return isPressed ? AppPalette.panelMuted : AppPalette.panelRaised
    }
}

private struct SettingsIconButtonStyle: ButtonStyle {
    @Environment(\.isEnabled) private var isEnabled
    var isDestructive = false

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: 13, weight: .semibold))
            .foregroundStyle(isDestructive ? AppPalette.destructive : AppPalette.textPrimary)
            .frame(width: 32, height: 32)
            .background(
                RoundedRectangle(cornerRadius: 8, style: .continuous)
                    .fill(isDestructive ? AppPalette.destructiveMuted : (configuration.isPressed ? AppPalette.panelMuted : AppPalette.panelRaised))
                    .overlay(
                        RoundedRectangle(cornerRadius: 8, style: .continuous)
                            .stroke(isDestructive ? AppPalette.destructive.opacity(0.30) : AppPalette.stroke, lineWidth: 1)
                    )
            )
            .scaleEffect(configuration.isPressed ? 0.985 : 1)
            .opacity(isEnabled ? 1 : 0.42)
    }
}

private struct SettingsCompactFieldModifier: ViewModifier {
    func body(content: Content) -> some View {
        content
            .textFieldStyle(.plain)
            .font(.system(size: 13, weight: .regular))
            .padding(.horizontal, 10)
            .padding(.vertical, 8)
            .background(
                RoundedRectangle(cornerRadius: 8, style: .continuous)
                    .fill(Color.white)
                    .overlay(
                        RoundedRectangle(cornerRadius: 8, style: .continuous)
                            .stroke(AppPalette.strongStroke.opacity(0.5), lineWidth: 1)
                    )
            )
            .foregroundStyle(AppPalette.textPrimary)
    }
}

private extension TextField {
    func settingsCompactField() -> some View {
        modifier(SettingsCompactFieldModifier())
    }
}

private enum AdminRulesPanel: String, CaseIterable, Identifiable {
    case workflow = "Как работает"
    case capabilities = "Возможности"
    case results = "Результаты"

    var id: String { rawValue }

    var icon: String {
        switch self {
        case .workflow: return "arrow.triangle.branch"
        case .capabilities: return "square.grid.2x2"
        case .results: return "checkmark.seal"
        }
    }
}

private struct AdminSettingsView: View {
    @ObservedObject var state: AppState
    @State private var selectedPanel: AdminRulesPanel = .workflow

    var body: some View {
        HStack(alignment: .top, spacing: 0) {
            VStack(alignment: .leading, spacing: 10) {
                Label("Содержание", systemImage: "list.bullet.rectangle")
                    .font(.system(size: 16, weight: .semibold))
                    .foregroundStyle(AppPalette.textPrimary)

                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 4) {
                        ForEach(AdminRulesPanel.allCases) { panel in
                            Button {
                                selectedPanel = panel
                            } label: {
                                Label(panel.rawValue, systemImage: panel.icon)
                                    .font(.system(size: 13, weight: .semibold))
                                    .foregroundStyle(selectedPanel == panel ? AppPalette.accent : AppPalette.textSecondary)
                                    .frame(maxWidth: .infinity, alignment: .leading)
                                    .padding(.horizontal, 8)
                                    .padding(.vertical, 7)
                                    .background(
                                        RoundedRectangle(cornerRadius: 6, style: .continuous)
                                            .fill(selectedPanel == panel ? AppPalette.accentMuted : Color.clear)
                                            .overlay(
                                                RoundedRectangle(cornerRadius: 6, style: .continuous)
                                                    .stroke(selectedPanel == panel ? AppPalette.accent.opacity(0.25) : Color.clear, lineWidth: 1)
                                            )
                                    )
                            }
                            .buttonStyle(.plain)
                        }
                    }
                    .padding(6)
                }
                .background(
                    RoundedRectangle(cornerRadius: 8, style: .continuous)
                        .fill(AppPalette.panelRaised)
                        .overlay(
                            RoundedRectangle(cornerRadius: 8, style: .continuous)
                                .stroke(AppPalette.stroke, lineWidth: 1)
                        )
                )
            }
            .padding(14)
            .frame(width: 248)
            .background(AppPalette.panel)

            Divider()
                .overlay(AppPalette.stroke)

            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    Label("Гайд по приложению", systemImage: "book.closed")
                        .font(.system(size: 20, weight: .semibold))
                        .foregroundStyle(AppPalette.textPrimary)

                    panelContent
                }
                .groupBoxStyle(AppGroupBoxStyle())
                .padding(16)
            }
        }
    }

    @ViewBuilder
    private var panelContent: some View {
        switch selectedPanel {
        case .workflow:
            workflowGuidePanel
        case .capabilities:
            capabilitiesGuidePanel
        case .results:
            resultsGuidePanel
        }
    }

    private var workflowGuidePanel: some View {
        VStack(alignment: .leading, spacing: 14) {
            GroupBox("Полный цикл сортировки") {
                VStack(spacing: 0) {
                    guideStep(1, title: "Подготовка", detail: "Выбирается исходная папка, место результата, имя архива и режим копирования или перемещения.")
                    guideStep(2, title: "Чтение документов", detail: "Приложение извлекает текст из PDF, изображений, таблиц и документов; при необходимости используется OCR.")
                    guideStep(3, title: "Определение документа", detail: "По содержимому находятся тип платежа, получатель, сотрудник, юрлицо, дата, номер и сумма.")
                    guideStep(4, title: "Выбор офиса", detail: "Найденные данные сопоставляются с сотрудниками, юрлицами, категориями и контрагентами офисов.")
                    guideStep(5, title: "Раскладка", detail: "Документ получает понятное безопасное имя и попадает в папку офиса и нужную категорию.")
                    guideStep(6, title: "Финальная обработка", detail: "После распределения формируются таблицы и объединенные PDF, а отдельные чеки переносятся из офисов в корневую папку исходников.", showDivider: false)
                }
            }

            GroupBox("Если документ не распознан") {
                VStack(spacing: 0) {
                    guideRow(icon: "tray.full", title: "Ручная проверка", detail: "Спорный файл не сортируется наугад и остается в отдельной очереди.")
                    guideRow(icon: "hand.tap", title: "Выбор готовых значений", detail: "Для файла выбираются офис, тип и категория из правил выбранного офиса.")
                    guideRow(icon: "doc.text.viewfinder", title: "Проверка реквизитов", detail: "Документ отображается рядом с полями сотрудника, даты и суммы. Исправления сохраняются кнопкой «Применить» и используются в итогах; суммы и даты не записываются в правила сотрудников.")
                    guideRow(icon: "arrow.clockwise", title: "Дообработка", detail: "После распределения всех файлов приложение сохраняет новые правила и завершает обработку.", showDivider: false)
                }
            }
        }
    }

    private var capabilitiesGuidePanel: some View {
        VStack(alignment: .leading, spacing: 14) {
            GroupBox("Документы") {
                VStack(spacing: 0) {
                    guideRow(icon: "arrow.triangle.branch", title: "Автоматическая сортировка", detail: "Распределение по офисам, категориям, сотрудникам и контрагентам на основе текста.")
                    guideRow(icon: "doc.on.doc", title: "Разбивка PDF", detail: "Создание отдельного PDF для каждой страницы исходного файла.")
                    guideRow(icon: "doc.richtext", title: "Объединение PDF", detail: "Сбор всех PDF выбранной папки в один файл с сохранением или удалением исходников.")
                    guideRow(icon: "text.viewfinder", title: "Распознавание текста", detail: "Чтение текстового слоя, метаданных и изображений с резервным OCR.", showDivider: false)
                }
            }

            GroupBox("Учет и контроль") {
                VStack(spacing: 0) {
                    guideRow(icon: "tablecells", title: "Зарплатные Excel", detail: "Обработка ведомостей XLS и XLSX, проверка сотрудников и создание файлов по офисам.")
                    guideRow(icon: "person.crop.circle.badge.questionmark", title: "Новые сотрудники", detail: "Таблицы создаются только после выбора офиса для каждого неизвестного сотрудника.")
                    guideRow(icon: "exclamationmark.arrow.triangle.2.circlepath", title: "Повторные выплаты", detail: "Одинаковые суммы одному сотруднику требуют решения; исключенный повтор сохраняется в ручной папке и не входит в расчеты.")
                    guideRow(icon: "building.columns", title: "Комиссии, налоги и взносы", detail: "Определение платежей, формирование итоговых таблиц и объединение чеков комиссий по офисам.")
                    guideRow(icon: "hand.raised", title: "Ручная корректировка", detail: "Контролируемое распределение нераспознанных документов без случайных папок.", showDivider: false)
                }
            }
        }
    }

    private var resultsGuidePanel: some View {
        VStack(alignment: .leading, spacing: 14) {
            GroupBox("Что создается в результате") {
                VStack(spacing: 0) {
                    guideRow(icon: "folder", title: "Архив по офисам", detail: "В каждом офисе остаются только категории, в которые реально попали документы.")
                    guideRow(icon: "doc.text", title: "Понятные имена", detail: "Файлы называются по данным документа; совпадающие имена не перезаписывают существующие файлы.")
                    guideRow(icon: "tablecells", title: "Таблицы и чеки", detail: "Создаются итоговые таблицы, а чеки зарплаты и комиссий объединяются в PDF в том же порядке.")
                    guideRow(icon: "archivebox", title: "Исходные чеки", detail: "Отдельные чеки зарплаты и комиссий хранятся в `Исходные_чеки / офис / категория` и не загромождают папки офисов.")
                    guideRow(icon: "checklist", title: "Итог обработки", detail: "Отчет перечисляет входные документы, обработанные файлы, исключенные повторы, ручную проверку и файлы, не найденные в архиве. Созданные таблицы и объединенные PDF не увеличивают число входных документов.")
                    guideRow(icon: "shippingbox", title: "Архив для Windows", detail: "Дополнительная ZIP-копия проходит проверку совместимости имен и форматов.", showDivider: false)
                }
            }

            GroupBox("Что влияет на точность") {
                VStack(spacing: 0) {
                    guideRow(icon: "building.2", title: "Юрлица офисов", detail: "Помогают определить офис для налогов, комиссий и платежей контрагентам.")
                    guideRow(icon: "person.2", title: "Список сотрудников", detail: "Используется для зарплатных документов и ведомостей.")
                    guideRow(icon: "person.text.rectangle", title: "Контрагенты и алиасы", detail: "Уточняют категорию и позволяют учитывать разные варианты названия поставщика.", showDivider: false)
                }
            }
        }
    }

    private func guideStep(_ number: Int, title: String, detail: String, showDivider: Bool = true) -> some View {
        HStack(alignment: .top, spacing: 13) {
            Text(String(format: "%02d", number))
                .font(.system(size: 11, weight: .bold, design: .monospaced))
                .foregroundStyle(AppPalette.accent)
                .frame(width: 34, height: 28)
                .background(AppPalette.accentMuted, in: RoundedRectangle(cornerRadius: 6, style: .continuous))
            guideText(title: title, detail: detail)
        }
        .padding(.vertical, 11)
        .overlay(alignment: .bottom) {
            if showDivider {
                Divider().overlay(AppPalette.stroke)
            }
        }
    }

    private func guideRow(icon: String, title: String, detail: String, showDivider: Bool = true) -> some View {
        HStack(alignment: .top, spacing: 13) {
            Image(systemName: icon)
                .font(.system(size: 15, weight: .semibold))
                .foregroundStyle(AppPalette.accent)
                .frame(width: 34, height: 28)
                .background(AppPalette.accentMuted, in: RoundedRectangle(cornerRadius: 6, style: .continuous))
            guideText(title: title, detail: detail)
        }
        .padding(.vertical, 11)
        .overlay(alignment: .bottom) {
            if showDivider {
                Divider().overlay(AppPalette.stroke)
            }
        }
    }

    private func guideText(title: String, detail: String) -> some View {
        VStack(alignment: .leading, spacing: 3) {
            Text(title)
                .font(.system(size: 13, weight: .semibold))
                .foregroundStyle(AppPalette.textPrimary)
            Text(detail)
                .font(.system(size: 11, weight: .medium))
                .foregroundStyle(AppPalette.textSecondary)
                .fixedSize(horizontal: false, vertical: true)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private var preferencesPanel: some View {
        VStack(alignment: .leading, spacing: 14) {
            GroupBox("Зарплатные таблицы") {
                VStack(alignment: .leading, spacing: 12) {
                    labeledField("Заголовок итогового столбца", text: $state.salaryTableTotalColumnTitle)
                    labeledField("Заголовок итоговой строки", text: $state.salaryTableTotalsRowTitle)
                }
            }

            GroupBox("Ручная проверка") {
                VStack(alignment: .leading, spacing: 12) {
                    Toggle("Сохранять читаемое имя файла, если текст распознан", isOn: $state.preserveReadableNamesInManualReview)
                    Toggle("Создавать отчет с причинами ручной обработки", isOn: $state.createManualReviewReport)
                }
            }

            GroupBox("Рабочие правила") {
                HStack(spacing: 12) {
                    Image(systemName: "building.2")
                        .font(.system(size: 18, weight: .semibold))
                        .foregroundStyle(AppPalette.accent)
                    VStack(alignment: .leading, spacing: 3) {
                        Text("Офисы, сотрудники и контрагенты")
                            .font(.system(size: 14, weight: .semibold))
                        Text("Настраиваются отдельно для каждого офиса")
                            .font(.system(size: 12, weight: .medium))
                            .foregroundStyle(AppPalette.textSecondary)
                    }
                    Spacer()
                    Button {
                        state.selectedSettingsSection = .offices
                    } label: {
                        Label("Открыть", systemImage: "arrow.right")
                    }
                    .buttonStyle(SettingsCompactButtonStyle())
                }
            }
        }
    }

    private var protectionPanel: some View {
        VStack(alignment: .leading, spacing: 14) {
            GroupBox("Сортировка") {
                VStack(spacing: 0) {
                    protectionRow("Анализ текста документа", detail: "Определяет тип, офис и контрагента")
                    protectionRow("Неопознанные документы", detail: "Направляются в ручную проверку")
                    protectionRow("Правила офисов", detail: "Учитываются до выбора итоговой папки", showDivider: false)
                }
            }

            GroupBox("Сохранность данных") {
                VStack(spacing: 0) {
                    protectionRow("Защита существующих файлов", detail: "Файлы не перезаписываются")
                    protectionRow("Безопасные имена", detail: "Совместимы с macOS и Windows")
                    protectionRow("Папки по факту", detail: "Пустая структура заранее не создается", showDivider: false)
                }
            }

            GroupBox("Обязательные результаты") {
                VStack(spacing: 0) {
                    protectionRow("Зарплатные таблицы", detail: "Формируются автоматически")
                    protectionRow("Налоги и взносы", detail: "Распознаются и попадают в Excel")
                    protectionRow("Комиссии и провайдеры", detail: "Определяются по тексту и правилам офиса", showDivider: false)
                }
            }
        }
    }

    private func protectionRow(_ title: String, detail: String, showDivider: Bool = true) -> some View {
        VStack(spacing: 0) {
            HStack(spacing: 12) {
                Image(systemName: "checkmark.circle.fill")
                    .font(.system(size: 17, weight: .semibold))
                    .foregroundStyle(AppPalette.success)
                VStack(alignment: .leading, spacing: 2) {
                    Text(title)
                        .font(.system(size: 13, weight: .semibold))
                        .foregroundStyle(AppPalette.textPrimary)
                    Text(detail)
                        .font(.system(size: 11, weight: .medium))
                        .foregroundStyle(AppPalette.textSecondary)
                }
                Spacer()
                Text("Всегда включено")
                    .font(.system(size: 10, weight: .semibold))
                    .foregroundStyle(AppPalette.accent)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 5)
                    .background(AppPalette.accentMuted, in: RoundedRectangle(cornerRadius: 6, style: .continuous))
            }
            .padding(.vertical, 10)
            if showDivider {
                Divider().overlay(AppPalette.stroke)
            }
        }
    }

    private var builderPanel: some View {
        GroupBox("Конструктор правил") {
            VStack(alignment: .leading, spacing: 12) {
                VStack(alignment: .leading, spacing: 8) {
                    Text("Как пользоваться")
                        .font(.system(size: 14, weight: .semibold))
                        .foregroundStyle(AppPalette.textPrimary)
                    Text("1. Включите нужный сценарий. 2. Если указано `Офисы -> ...`, перейдите в `Офисы` и заполните это поле. 3. Нажмите `Сохранить`. Текст правила руками писать не нужно: приложение сохранит его само.")
                        .font(.system(size: 13, weight: .medium))
                        .foregroundStyle(AppPalette.textPrimary)
                        .fixedSize(horizontal: false, vertical: true)
                    Button {
                        state.selectedSettingsSection = .offices
                    } label: {
                        Label("Открыть офисы", systemImage: "building.2")
                    }
                    .buttonStyle(SettingsCompactButtonStyle())
                }
                .padding(12)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(
                    RoundedRectangle(cornerRadius: 8, style: .continuous)
                        .fill(AppPalette.accentMuted)
                        .overlay(
                            RoundedRectangle(cornerRadius: 8, style: .continuous)
                                .stroke(AppPalette.strongStroke, lineWidth: 1)
                        )
                )

                RuleBuilderCard(
                    title: "НДФЛ, ЕНП и взносы по офису",
                    systemImage: "doc.text.magnifyingglass",
                    isOn: $state.taxesUseOfficeEntityRouting,
                    writeAt: "`Офисы` -> выберите офис -> поле `Юрлицо`; ниже включите категорию `Ндфл и Взносы`.",
                    ruleText: "`Налоги и взносы стараются попасть в офис по юрлицу документа.`",
                    result: "Если в документе найдено юрлицо этого офиса, файл попадет в `Офис / Ндфл и Взносы`."
                )
                RuleBuilderCard(
                    title: "Распознавать налоговые платежи по тексту",
                    systemImage: "text.magnifyingglass",
                    isOn: $state.taxesDetectedByPaymentPhrases,
                    writeAt: "Ничего заполнять не нужно. Включите сценарий и нажмите `Сохранить`.",
                    ruleText: "`Налоги, НДФЛ, ЕНП и страховые взносы определяются по платежным формулировкам документа.`",
                    result: "Документы с формулировками НДФЛ, ЕНП, взносов и налогов будут относиться к налоговой категории."
                )
                RuleBuilderCard(
                    title: "Контрагент определяет категорию",
                    systemImage: "person.text.rectangle",
                    isOn: $state.useContractorsAsCategorySignals,
                    writeAt: "`Офисы` -> выберите офис -> `Контрагенты по категориям`; напишите контрагента в нужной категории.",
                    ruleText: "`Контрагент из правил офиса усиливает выбор категории и папки.`",
                    result: "Если в документе найден этот контрагент, система увереннее выберет указанную категорию офиса."
                )
                RuleBuilderCard(
                    title: "Комиссии по юрлицу офиса",
                    systemImage: "building.columns",
                    isOn: $state.commissionsUseOfficeEntityRouting,
                    writeAt: "`Офисы` -> выберите офис -> поле `Юрлицо`; ниже включите категорию `Комиссии`.",
                    ruleText: "`Комиссии стараются попасть в офис по юрлицу документа, даже если в имени файла это не видно.`",
                    result: "Если в документе комиссии найдено юрлицо этого офиса, файл попадет в `Офис / Комиссии`."
                )
                RuleBuilderCard(
                    title: "Неуверенные документы в ручную проверку",
                    systemImage: "hand.raised",
                    isOn: $state.unresolvedRouteGoesToManualReview,
                    writeAt: "Ничего заполнять не нужно. Включите сценарий и нажмите `Сохранить`.",
                    ruleText: "`Если после всех проверок путь не собран уверенно, файл уходит в Требует_ручной_проверки.`",
                    result: "Спорные документы не будут раскладываться наугад, а попадут в ручную проверку."
                )
                RuleBuilderCard(
                    title: "Интернет-провайдеры",
                    systemImage: "wifi",
                    isOn: $state.internetPrioritizeKnownProviders,
                    writeAt: "Обычно ничего заполнять не нужно. Для исключений: `Офисы` -> `Контрагенты по категориям` -> `Интернет`.",
                    ruleText: "`Известные провайдеры и телеком-компании приоритетно относятся к категории Интернет.`",
                    result: "Счета известных провайдеров будут попадать в категорию `Интернет`."
                )
                RuleBuilderCard(
                    title: "Контрагенты по отдельным папкам",
                    systemImage: "folder.badge.person.crop",
                    isOn: $state.internetCreateSubfoldersByOfficeContractors,
                    writeAt: "`Офисы` -> выберите офис -> `Контрагенты по категориям`; у нужного контрагента включите `Создавать папку`.",
                    ruleText: "`Для контрагентов с включенной настройкой Создавать папку приложение создает подпапку внутри категории.`",
                    result: "Файл попадет в `Офис / Категория / Контрагент`, если найден один из его алиасов."
                )
            }
        }
    }

    private var guidePanel: some View {
        GroupBox("Гайд и база") {
            VStack(alignment: .leading, spacing: 16) {
                EditableStringListEditor(
                    title: "Назначение файла",
                    placeholder: "Строка описания",
                    addLabel: "Добавить строку",
                    values: $state.generalPurposeLines
                )
                EditableStringListEditor(
                    title: "Общие принципы",
                    placeholder: "Новое правило",
                    addLabel: "Добавить принцип",
                    values: $state.generalPrinciples
                )
                EditableStringListEditor(
                    title: "Порядок определения папки",
                    placeholder: "Новый шаг",
                    addLabel: "Добавить шаг",
                    values: $state.generalFolderOrder
                )
                EditableStringListEditor(
                    title: "Дополнительные обработчики",
                    placeholder: "Новый обработчик",
                    addLabel: "Добавить обработчик",
                    values: $state.generalExtraHandlers
                )
            }
        }
    }

    private var criticalPanel: some View {
        GroupBox("Критически важные настройки") {
            VStack(alignment: .leading, spacing: 12) {
                Toggle("Если текст документа читается, опираться на него раньше, чем на имя файла", isOn: $state.routeByDocumentTextFirst)
                Toggle("Если уверенного пути нет, отправлять файл в ручную проверку", isOn: $state.unresolvedRouteGoesToManualReview)
                Toggle("Не создавать пустые папки заранее", isOn: $state.doNotCreateEmptyFoldersInAdvance)
                Toggle("Создавать папки только при первой реальной раскладке документа", isOn: $state.createFoldersOnlyWhenDocumentsExist)
                Toggle("Автоматически делать имена безопасными для Windows и macOS", isOn: $state.namingMakeWindowsSafe)
                Toggle("Создавать `_report.txt` с причинами ручной обработки", isOn: $state.createManualReviewReport)
                Toggle("Создавать `Зарплата_<офис>.xlsx` автоматически", isOn: $state.salaryTableEnabled)
            }
        }
    }

    private var sortingPanel: some View {
        GroupBox("Настройки сортинга") {
            VStack(alignment: .leading, spacing: 10) {
                Toggle("Если текст документа читается, опираться на него раньше, чем на имя файла", isOn: $state.routeByDocumentTextFirst)
                Toggle("Сначала пытаться понять офис, потом окончательно фиксировать категорию", isOn: $state.routeOfficeBeforeCategoryFinalization)
                Toggle("Использовать контрагентов из правил офисов как усиление для выбора категории", isOn: $state.useContractorsAsCategorySignals)
                Toggle("Если уверенного пути нет, отправлять файл в ручную проверку", isOn: $state.unresolvedRouteGoesToManualReview)
            }
        }
    }

    private var foldersPanel: some View {
        GroupBox("Создание папок") {
            VStack(alignment: .leading, spacing: 16) {
                EditableStringListEditor(
                    title: "Структура архива",
                    placeholder: "Новая папка",
                    addLabel: "Добавить папку",
                    values: $state.generalArchiveFolders
                )
                Toggle("Создавать папки только при первой реальной раскладке документа", isOn: $state.createFoldersOnlyWhenDocumentsExist)
                Toggle("Не создавать пустые папки заранее", isOn: $state.doNotCreateEmptyFoldersInAdvance)
                Toggle("Создавать `Требует_ручной_проверки` только когда она реально нужна", isOn: $state.createManualReviewFolderOnlyWhenNeeded)
                Toggle("Создавать специальные подпапки только при срабатывании маршрутизации", isOn: $state.createSpecialSubfoldersByRoutingRules)
                Toggle("При конфликте имен делать уникальный суффикс", isOn: $state.protectExistingFilesWithUniqueSuffix)
            }
        }
    }

    private var salaryPanel: some View {
        GroupBox("Зарплаты") {
            VStack(alignment: .leading, spacing: 10) {
                Toggle("Создавать `Зарплата_<офис>.xlsx` автоматически", isOn: $state.salaryTableEnabled)
                Label("Один столбец на каждую фактическую дату выплаты", systemImage: "calendar")
                labeledField("Заголовок итогового столбца", text: $state.salaryTableTotalColumnTitle)
                labeledField("Заголовок итоговой строки", text: $state.salaryTableTotalsRowTitle)
            }
        }
    }

    private var namingPanel: some View {
        GroupBox("Именование файлов") {
            VStack(alignment: .leading, spacing: 10) {
                Toggle("Собирать имя из текста документа, если поля найдены", isOn: $state.namingUseExtractedText)
                Toggle("Если текста не хватает, использовать безопасный fallback от исходного имени", isOn: $state.namingFallbackToOriginalWhenNoText)
                Toggle("Автоматически делать имена безопасными для Windows и macOS", isOn: $state.namingMakeWindowsSafe)
                Toggle("При занятом имени добавлять уникальный суффикс", isOn: $state.namingKeepUniqueSuffixOnConflict)
                labeledField("Формат имени файла", text: $state.generalNamingFormat)
            }
        }
    }

    private var manualReviewPanel: some View {
        GroupBox("Ручная проверка") {
            VStack(alignment: .leading, spacing: 10) {
                Toggle("Отправлять в ручную проверку документы с низкой уверенностью", isOn: $state.sendLowConfidenceDocumentsToManualReview)
                Toggle("Если офис не найден, отправлять в ручную проверку", isOn: $state.sendMissingOfficeDocumentsToManualReview)
                Toggle("В ручной проверке сохранять читаемое имя из текста", isOn: $state.preserveReadableNamesInManualReview)
                Toggle("Создавать `_report.txt` с причинами ручной обработки", isOn: $state.createManualReviewReport)
            }
        }
    }

    private var commissionsPanel: some View {
        GroupBox("Комиссии") {
            VStack(alignment: .leading, spacing: 10) {
                Toggle("Определять банковские комиссии по тексту платежа", isOn: $state.commissionsDetectedByPaymentText)
                Toggle("Пытаться определить офис комиссии по юрлицу документа", isOn: $state.commissionsUseOfficeEntityRouting)
                Toggle("Создавать `Комиссии_<офис>.xlsx`", isOn: $state.commissionsCreateOfficeExcel)
            }
        }
    }

    private var taxesPanel: some View {
        GroupBox("Налоги и взносы") {
            VStack(alignment: .leading, spacing: 10) {
                Toggle("Определять НДФЛ, ЕНП и взносы по платежным формулировкам", isOn: $state.taxesDetectedByPaymentPhrases)
                Toggle("Пытаться определить офис налогов и взносов по юрлицу", isOn: $state.taxesUseOfficeEntityRouting)
                Toggle("Создавать Excel по налогам и взносам", isOn: $state.taxesCreateTaxAndInsuranceExcel)
            }
        }
    }

    private var internetPanel: some View {
        GroupBox("Интернет и провайдеры") {
            VStack(alignment: .leading, spacing: 10) {
                Toggle("Известных провайдеров относить к `Интернет` приоритетно", isOn: $state.internetPrioritizeKnownProviders)
                Toggle("Разрешать специальные подпапки провайдеров внутри `Интернет`", isOn: $state.internetAllowSpecialProviderSubfolders)
                Toggle("Разрешать подпапки по контрагентам с включенной настройкой", isOn: $state.internetCreateSubfoldersByOfficeContractors)
                Toggle("Исправлять битый OCR и сломанную кодировку названий провайдеров", isOn: $state.internetNormalizeBrokenProviderText)
            }
        }
    }

    private var extraPanel: some View {
        GroupBox("Прочие и редкие правила") {
            VStack(alignment: .leading, spacing: 16) {
                EditableStringListEditor(
                    title: "Прочие таблицы",
                    placeholder: "Новое правило таблиц",
                    addLabel: "Добавить правило",
                    values: $state.generalTableRules
                )
                EditableStringListEditor(
                    title: "Плохо читаемые файлы",
                    placeholder: "Новое правило",
                    addLabel: "Добавить правило",
                    values: $state.generalLowQualityRules
                )
                EditableStringListEditor(
                    title: "Общие специальные правила",
                    placeholder: "Новое специальное правило",
                    addLabel: "Добавить правило",
                    values: $state.specialRules
                )
            }
        }
    }

    @ViewBuilder
    private func labeledField(_ title: String, text: Binding<String>) -> some View {
        HStack {
            Text(title)
                .frame(width: 250, alignment: .leading)
                .foregroundStyle(AppPalette.textSecondary)
            TextField(title, text: text)
                .appField()
        }
    }
}

private struct EditableStringListEditor: View {
    let title: String
    let placeholder: String
    let addLabel: String
    @Binding var values: [String]

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title)
                .font(.system(size: 18, weight: .semibold, design: .rounded))
                .foregroundStyle(AppPalette.textPrimary)
            ForEach(Array(values.enumerated()), id: \.offset) { index, _ in
                HStack(spacing: 8) {
                    TextField(placeholder, text: binding(index))
                        .appField()
                    Button(role: .destructive) {
                        values.remove(at: index)
                    } label: {
                        Image(systemName: "trash")
                    }
                    .buttonStyle(AppSecondaryButtonStyle())
                }
            }
            Button(addLabel) {
                values.append("")
            }
            .buttonStyle(AppSecondaryButtonStyle())
        }
    }

    private func binding(_ index: Int) -> Binding<String> {
        Binding(
            get: { values.indices.contains(index) ? values[index] : "" },
            set: { newValue in
                guard values.indices.contains(index) else { return }
                values[index] = newValue
            }
        )
    }
}
