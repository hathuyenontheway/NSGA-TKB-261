# Đặt tả
1. Mục tiêu bài toán
Sinh viên đăng ký môn học theo nhóm lớp của mình (lớp chính quy, chất lượng cao, tài năng, tiếng Nhật + Khả năng của Khoa mở lớp nào + Kế hoạch giảng dạy
Phòng Đào Tạo lấy những môn học được đăng ký + Constraint -> bắt đầu phân chia lớp. 
2.1. Chia Các lớp học trước (Trong bước này là gán GV giả hoặc có một số lớp thì chỉ có 1 GV dạy gán cứng với lớp đó luôn)
Tạo ra danh sách các lớp học phần cho từng môn học được mở trong kỳ và xếp lịch sơ bộ cho các lớp học này, sao cho:
Xác định số lớp cần mở cho mỗi môn dựa trên số lượng sinh viên đăng ký, kế hoạch giảng dạy và loại hình lớp.
Gán cho mỗi lớp học phần: Mã nhóm lớp, loại lớp (LT/Lab), phòng học, thời gian học, tuần học.
Các lớp này được sắp xếp sao cho thỏa mãn ràng buộc cứng, tối ưu hóa ràng buộc mềm, tạo ra đầu ra hợp lệ cho bài toán 2.

# Data
1. **chmh.csv**
```
ID   STT DANGMON                MAU  \
0     1     1      LT      1_0.8_0_0_0.2   
1     2     2      LT  1.5_0.93_0_0_0.57   
2     3     3      LT      2_1.4_0_0_0.6   
3     4     4      LT      2_1.4_0_0.6_0   
4     5     5      LT      2_1.6_0_0_0.4   
..  ...   ...     ...                ...   
76   66    66    TTNT     2_0_0_0_2_ttnt   
77   67    67    TTNT     3_0_0_0_3_ttnt   
78   68    68    TTNT     6_0_0_0_6_ttnt   
79   81  9999      LT               TEST   
80  142  1000     JPN      0_0_0_0_0_JPN   

                                             CHUTHICH  PBSOTIET_TONG  \
0   0.8LT (2 tiết/tuần x 6 tuần) + 0.2BTL (9 giờ/b...             50   
1    0.93LT (2 tiết/tuần x 7 tuần) + 0.57BTL (25.65g)             75   
2   1.4LT (3 tiết/tuần x 7 tuần) + 0.6BTL (9 giờ/b...            100   
3          1.4LT (3 tiết/tuần x 7 tuần) + 0.6TN (18g)            100   
4   1.6LT (2 tiết/tuần x 12 tuần) + 0.4BTL (9 giờ/...            100   
..                                                ...            ...   
76                              Thực tập ngoài trường            200   
77                              Thực tập ngoài trường            300   
78                              Thực tập ngoài trường            600   
79                                      Cấu hình test             55   
80                                  Tiếng Nhật (ĐHNB)            400   

    PBSOTIET_LT  PBSOTIET_BT  PBSOTIET_TN  PBSOTIET_BTL  ...  PBSOTC_BT  \
0            12            0            0             9  ...        0.0   
1            14            0            0            26  ...        0.0   
2            21            0            0            27  ...        0.0   
3            21            0           18             0  ...        0.0   
4            24            0            0            18  ...        0.0   
..          ...          ...          ...           ...  ...        ...   
76            0            0            0             0  ...        0.0   
77            0            0            0             0  ...        0.0   
78            0            0            0             0  ...        0.0   
79            1            2            3             4  ...        9.0   
80           90           60            0             0  ...        0.0   

    PBSOTC_TN  PBSOTC_BTL  PBSOTC_TQ  PBSOTC_DA  PBSOTC_TTNT  PBSOTC_LVTN  \
0         0.0        0.20          0          0            0          0.0   
1         0.0        0.57          0          0            0          0.0   
2         0.0        0.60          0          0            0          0.0   
3         0.6        0.00          0          0            0          0.0   
4         0.0        0.40          0          0            0          0.0   
..        ...         ...        ...        ...          ...          ...   
76        0.0        0.00          0          0            2          0.0   
77        0.0        0.00          0          0            3          0.0   
78        0.0        0.00          0          0            6          0.0   
79        8.0        7.00          6          5            4          3.0   
80        0.0        0.00          0          0            0          0.0   

    PBSOTC_TUHOC  PBSOTC_KHAC  MAU_OLD  
0              0            0       1a  
1              0            0       1b  
2              0            0       2c  
3              0            0       2b  
4              0            0       2a  
..           ...          ...      ...  
76             0            0    ttnt2  
77             0            0    ttnt3  
78             0            0    ttnt6  
79             2            1        *  
80             0            0      NaN  

[81 rows x 28 columns]
```
2. **kq_nv.csv**
```
F_MANH  F_DVHT    MAU           MADCMH  F_MAMH F_MAKH  F_MASV  \
0        N---       3     3a  DCMH.AS1001.8.1  AS1001     UD       1   
1        N---       3     3a  DCMH.AS1001.8.1  AS1001     UD       2   
2        N---       3     3a  DCMH.AS1001.8.1  AS1001     UD       3   
3        N---       3     3a  DCMH.AS1001.8.1  AS1001     UD       4   
4        N---       3     3a  DCMH.AS1001.8.1  AS1001     UD       5   
...       ...     ...    ...              ...     ...    ...     ...   
111526   N---       9  lvtn9  DCMH.TR4317.3.1  TR4317     GT   18899   
111527   N---       9  lvtn9  DCMH.TR4317.3.1  TR4317     GT   18903   
111528   N---       4  lvtn4  DCMH.TR4347.6.1  TR4347     GT   18904   
111529   N---       4  lvtn4  DCMH.TR4347.6.1  TR4347     GT   18905   
111530   N---       4  lvtn4  DCMH.TR4347.6.1  TR4347     GT   18865   

       F_HIENDIEN  KHOA  F_TENLOP HTDT KHGD F_DV  CHTRDT  LHMH  
0             NaN  23.0  KU23KYS1   CQ  NaN   UD     NaN    LT  
1             NaN  24.0  UD24KDL1   CQ  NaN   UD     NaN    LT  
2               D  25.0  CK25COD2   CQ  NaN   CK     NaN    LT  
3             NaN  25.0  HC25HTS3   CQ  NaN   HC     NaN    LT  
4             NaN  25.0  DC25DXD1   CQ  NaN   DC     NaN    LT  
...           ...   ...       ...  ...  ...  ...     ...   ...  
111526          D  18.0   BT18KTO   CQ  NaN  NaN     NaN  LVTN  
111527        NaN  18.0   BT18KTO   CQ  NaN  NaN     NaN  LVTN  
111528        NaN  22.0  KC22OTL2   CQ  NaN  NaN     NaN  LVTN  
111529        NaN  22.0  KC22OTL2   CQ  NaN  NaN     NaN  LVTN  
111530        NaN  21.0   BT21KTO   CQ  NaN  NaN     NaN  LVTN  

[111531 rows x 15 columns]
```
3. **mh.csv**
```
MAKEM    MAMH                     TENMH  \
0       NaN  003001  ANH VAN 1                  
1       NaN  003002  ANH VAN 2                  
2       NaN  003003  ANH VAN 3                  
3       NaN  003004  ANH VAN 4                  
4       NaN  003005  PHAP VAN 1                 
...     ...     ...                       ...   
13421   NaN  U4109T  NETWORK FUNDAMENTALS(Tut   
13422   NaN  U42028  DEEP LEARNING AND CONVOL   
13423   NaN  U43030  PROFESSIONAL PRACTICE IN   
13424   NaN  U48024  PROGRAMMING 2              
13425   NaN  U48433  SOFTWARE ARCHITECTURE      

                                               TENMH_ENG MASUBJECTAREA  SOTC  \
0      English 1                                     ...            LA     2   
1      English 2                                     ...            LA     2   
2      English 3                                     ...            LA     2   
3      English 4                                     ...            LA     2   
4      French 1                                      ...            LA     2   
...                                                  ...           ...   ...   
13421  Network Fundamentals (Tutorial)               ...            U4     0   
13422  Deep Learning and Convolution Neural Netwo    ...            U4    38   
13423  Professional Practice in Computing            ...            U4    38   
13424  Programming 2                                 ...            U4    38   
13425  Software Architecture                         ...            U4    38   

       SOTC_HP  SOTIET  SOTIET_XEPTKB loai_mh  f_lt  f_bt  f_tn  f_btl  f_da  \
0            2     675             45    Prsn     0    45     0    225     0   
1            2     675             45    Prsn     0    45     0    225     0   
2            2     675             45    Prsn     0    45     0    225     0   
3            2     675             45    Prsn     0    45     0    225     0   
4            2      60             60    Prsn     0    60     0      0     0   
...        ...     ...            ...     ...   ...   ...   ...    ...   ...   
13421        0       0             30     Lab     0     0    30      0     0   
13422       38       0              0     NaN     0     0     0      0     0   
13423       38       0              0     NaN     0     0     0      0     0   
13424       38       0              0     NaN     0     0     0      0     0   
13425       38       0              0     NaN     0     0     0      0     0   

       f_la  f_tq f_makh  mau  
0         0     0     TN  NaN  
1         0     0     TN  NaN  
2         0     0     TN  NaN  
3         0     0     TN  NaN  
4         0     0     TN  NaN  
...     ...   ...    ...  ...  
13421     0     0     MT  NaN  
13422     0     0     MT  NaN  
13423     0     0     MT  NaN  
13424     0     0     MT  NaN  
13425     0     0     MT  NaN  

[13426 rows x 19 columns]
```
# Các CTDL đã thiết kế
1. ```calendar.py```

```
from dataclasses import dataclass

@dataclass(slots=True)
class AcademicWeek:
    week: int
    is_teaching: bool
    is_midterm: bool
    is_final: bool
    is_holiday: bool
```
2. ```chromosome.py```
```from dataclasses import dataclass, field

from models.gene import Gene


@dataclass(slots=True)
class Chromosome:
    genes: list[Gene] = field(default_factory=list)

    rank: int = 0
    crowding_distance: float = 0.0

    objectives: tuple[float, ...] = field(default_factory=tuple)

    hard_constraint_violation: int = 0

    def __len__(self) -> int:
        return len(self.genes)

    def __getitem__(self, index: int) -> Gene:
        return self.genes[index]

    def append(self, gene: Gene) -> None:
        self.genes.append(gene)

    def copy(self) -> "Chromosome":
        return Chromosome(
            genes=[
                Gene(
                    session_id=g.session_id,
                    room_id=g.room_id,
                    day=g.day,
                    start_slot=g.start_slot,
                    start_week=g.start_week,
                )
                for g in self.genes
            ],
            rank=self.rank,
            crowding_distance=self.crowding_distance,
            objectives=self.objectives,
            hard_constraint_violation=self.hard_constraint_violation,
        )
```
3. ```courses.py```
```
from dataclasses import dataclass
from models.session import SessionPattern
@dataclass(slots=True)
class Course:
    course_id: str
    course_name: str
    
    faculty_id: str
    faculty_name: str
    
    credits: int
    total_hours: int
    
    lecture_hours: int
    exercise_hours: int
    lab_hours: int
    project_hours: int
    assignment_hours: int
    thesis_hours: int
    
    lecture_pattern: SessionPattern | None
    lab_pattern: SessionPattern | None
```
4. ```room.py```
```
from dataclasses import dataclass

@dataclass(slots=True)
class Room:
    room_id: str
    campus: int
    capacity: int
    room_type: str
```
# ```section.py```
```
from dataclasses import dataclass

@dataclass(slots=True)
class Section:
    section_id: str
    course_id: str
    program_type: str
    expected_students: int
    max_capacity: int
    has_lab: bool
```
5. ```session.py```
```
from dataclasses import dataclass

@dataclass(slots=True)
class SessionPattern:
    slots: int
    weeks: int

@dataclass(slots=True)
class SessionMetadata:
    session_id: int
    course_id: str
    section_id: str
    session_type: str           # lecture / lab                    
    class_size: int
    allowed_rooms: list
    linked_session_id: int | None
    campus: int
```